import streamlit as st
import os
import subprocess
import urllib.request
import re
import google.generativeai as genai

# ==========================================
# 1. THE AI PARSER (Backend)
# ==========================================
class LexiCiteParser:
    def __init__(self, api_key):
        """Initializes the AI parser with the provided Gemini API key."""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_bibtex(self, source_list):
        """Sends the raw text list to the LLM and enforces a strict BibTeX output."""
        system_prompt = f"""
        You are an expert legal data parser adhering to OSCOLA standards.
        Convert the following numbered list of legal sources into a valid BibTeX database.
        
        CRITICAL RULES:
        1. The BibTeX citation key for each entry MUST strictly be "source" followed by its number in the list (e.g., source1, source2).
        2. Accurately categorize cases as @misc or @jurisdiction, books as @book, articles as @article.
        3. Output ONLY the raw BibTeX code. Do not use markdown formatting (like ```bibtex), do not add introductory or concluding remarks. Just the pure text database.
        
        SOURCE LIST:
        {source_list}
        """
        try:
            response = self.model.generate_content(system_prompt)
            clean_bibtex = response.text.replace('```bibtex', '').replace('```', '').strip()
            
            if not clean_bibtex.startswith('@'):
                raise ValueError("The AI did not return valid BibTeX format.")
            return clean_bibtex
        except Exception as e:
            raise Exception(f"AI Parsing Failed: {str(e)}")


# ==========================================
# 2. THE OSCOLA ENGINE (Backend)
# ==========================================
class LexiCiteEngine:
    def __init__(self, csl_url="[https://raw.githubusercontent.com/citation-style-language/styles/master/oscola.csl](https://raw.githubusercontent.com/citation-style-language/styles/master/oscola.csl)"):
        self.csl_filename = "oscola.csl"
        self.csl_url = csl_url
        self._ensure_csl()

    def _ensure_csl(self):
        """Downloads the official OSCOLA ruleset if it isn't already in the folder."""
        if not os.path.exists(self.csl_filename):
            urllib.request.urlretrieve(self.csl_url, self.csl_filename)

    def _to_unicode_super(self, num_str):
        """Converts standard string numbers to Unicode superscripts."""
        super_map = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹'}
        return "".join([super_map[char] for char in num_str])

    def format_document(self, docx_bytes, bibtex_data, num_sources):
        """Processes the Word document, BibTeX, and applies OSCOLA logic."""
        input_docx = "temp_input.docx"
        md_file = "temp_draft.md"
        bib_file = "library.bib"
        output_docx = "LexiCite_Formatted.docx"

        try:
            # Write files
            with open(bib_file, "w", encoding="utf-8") as f:
                f.write(bibtex_data)
            with open(input_docx, "wb") as f:
                f.write(docx_bytes)

            # Convert to Markdown
            subprocess.run(["pandoc", input_docx, "-t", "markdown", "-o", md_file], capture_output=True, text=True, check=True)

            # Read Markdown
            with open(md_file, "r", encoding="utf-8") as f:
                md_text = f.read()

            # Mapping Logic
            mapped_nums = [str(i) for i in range(1, num_sources + 1)]
            sorted_nums = sorted(mapped_nums, key=len, reverse=True)
            footnote_appendix = "\n\n"

            for num in sorted_nums:
                key = f"source{num}"
                footnote_marker = f"[^{num}]"
                
                unicode_sup = self._to_unicode_super(str(num))
                md_text = md_text.replace(unicode_sup, footnote_marker)
                md_text = re.sub(r'\^\s*' + re.escape(str(num)) + r'\s*\^', footnote_marker, md_text)
                md_text = re.sub(r'\\?\[\s*' + re.escape(str(num)) + r'\s*\\?\]', footnote_marker, md_text)
                md_text = re.sub(r'\(\s*' + re.escape(str(num)) + r'\s*\)', footnote_marker, md_text)
                md_text = re.sub(r'<\s*sup\s*>\s*' + re.escape(str(num)) + r'\s*<\s*/\s*sup\s*>', footnote_marker, md_text, flags=re.IGNORECASE)
                
                footnote_appendix += f"[^{num}]: [@{key}]\n\n"

            md_text += footnote_appendix
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_text)

            # Pandoc Compilation
            result = subprocess.run([
                "pandoc", md_file, 
                "--citeproc", 
                f"--bibliography={bib_file}", 
                f"--csl={self.csl_filename}", 
                "-M", "suppress-bibliography=true", 
                "-o", output_docx
            ], capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(f"Pandoc Compilation Error: {result.stderr}")

            return output_docx

        finally:
            for file in [input_docx, md_file, bib_file]:
                if os.path.exists(file):
                    os.remove(file)


# ==========================================
# 3. THE FRONTEND UI (Streamlit)
# ==========================================
st.set_page_config(page_title="LexiCite Engine", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# CSS Styling
st.markdown("""
<style>
    @import url('[https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap](https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap)');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 95%; }

    .main-title {
        font-weight: 800; font-size: 3.5rem; margin-bottom: 0rem; letter-spacing: -0.03em;
        background: linear-gradient(135deg, #8B1A1A 0%, #D2B48C 100%); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .main-subtitle { color: #94A3B8; font-size: 1.2rem; font-weight: 500; margin-bottom: 2rem; letter-spacing: -0.01em; }

    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #8B1A1A 0%, #A52A2A 100%);
        color: white; border-radius: 12px; padding: 0.8rem 2rem; font-size: 1.1rem;
        font-weight: 600; border: none; box-shadow: 0 4px 20px rgba(139, 26, 26, 0.4);
        transition: all 0.3s ease; width: 100%; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .stButton>button[kind="primary"]:hover { transform: translateY(-3px); box-shadow: 0 8px 30px rgba(139, 26, 26, 0.6); }

    .stTextArea textarea {
        border-radius: 10px; padding: 1rem; font-size: 1rem; line-height: 1.6; transition: all 0.3s;
        border: 1px solid rgba(156, 163, 175, 0.3);
    }
    .stTextArea textarea:focus { border-color: #8B1A1A; box-shadow: 0 0 0 3px rgba(139, 26, 26, 0.2); }
</style>
""", unsafe_allow_html=True)

# Header
col_logo, col_text = st.columns([1, 8])
with col_logo:
    if os.path.exists("LexiCite.jpg"):
        st.image("LexiCite.jpg", use_container_width=True)
with col_text:
    st.markdown("<div class='main-title'>LexiCite</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-subtitle'>Standalone OSCOLA Engine with AI Parsing</div>", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    if os.path.exists("LexiCite.jpg"):
        st.image("LexiCite.jpg", use_container_width=True)
        st.markdown("---")
        
    st.markdown("## 🧠 AI Brain Setup")
    st.caption("Enter your free Google Gemini API key to activate the parser.")
    api_key = st.text_input("Gemini API Key", type="password")
    st.markdown("[Get a free key here](https://aistudio.google.com/app/apikey)")

# Main Application Logic
if not api_key:
    st.markdown("""
    <div style='text-align: center; padding: 4rem 2rem; background-color: #f8fafc; border-radius: 16px; border: 1px dashed #cbd5e1; margin-top: 2rem;'>
        <h2>Welcome to the LexiCite Engine</h2>
        <p style='color: #64748b; font-size: 1.1rem;'>Please enter your Gemini API Key in the sidebar to activate the citation parser.</p>
    </div>
    """, unsafe_allow_html=True)

else:
    col1, col2 = st.columns(2, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 📄 Step 1: Upload Draft (.docx)")
            st.caption("Upload your Word document containing footnote markers (e.g. [1], ¹, ^1^).")
            uploaded_file = st.file_uploader("Upload Word Document", type=["docx"], label_visibility="collapsed")

    with col2:
        with st.container(border=True):
            st.markdown("### 📚 Step 2: Paste Source List")
            st.caption("Paste your numbered list of sources. The AI will convert them automatically.")
            source_list = st.text_area("Source List", height=200, placeholder="1. Agbaje v Commissioner of Police (1969) 1 NMLR 137\n2. Malemi E, The Nigerian Constitutional Law (2012)")

    st.write("") 

    col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

    with col_center:
        if st.button("⚡ Parse & Compile Document", type="primary"):
            if uploaded_file is None or not source_list.strip():
                st.warning("⚠️ Please upload your .docx file and paste your source list to proceed.")
            else:
                with st.status("Initializing LexiCite Engine...", expanded=True) as status:
                    try:
                        # STAGE 1: AI PARSING
                        st.write("🧠 AI is parsing and structuring your sources...")
                        ai_parser = LexiCiteParser(api_key=api_key)
                        bibtex_data = ai_parser.generate_bibtex(source_list)
                        num_sources = len([line for line in source_list.split('\n') if line.strip()])

                        # STAGE 2: OSCOLA ENGINE
                        st.write("⚙️ Running LexiCite Engine (Applying OSCOLA logic)...")
                        engine = LexiCiteEngine()
                        formatted_doc_path = engine.format_document(
                            docx_bytes=uploaded_file.getbuffer(),
                            bibtex_data=bibtex_data,
                            num_sources=num_sources
                        )
                        
                        status.update(label="Compilation Complete!", state="complete", expanded=False)
                        st.balloons()
                        
                        with st.expander("View AI-Generated BibTeX Data"):
                            st.code(bibtex_data, language="bibtex")
                        
                        col_met1, col_met2 = st.columns(2)
                        col_met1.metric(label="Sources Formatted", value=f"{num_sources}")
                        col_met2.metric(label="Document Status", value="Ready")
                        
                        with open(formatted_doc_path, "rb") as file:
                            st.download_button("📥 Download Formatted Document", file, "LexiCite_Formatted.docx", use_container_width=True)
                    
                    except Exception as e:
                        status.update(label="System Error Occurred", state="error", expanded=True)
                        st.error(f"System Error: {e}")