import streamlit as st
import os
import subprocess
import urllib.request
import re

# ==========================================
# 1. THE LOCAL HEURISTIC PARSER (Backend)
# ==========================================
class LexiCiteParser:
    def __init__(self):
        pass

    def generate_bibtex(self, source_list):
        lines = [line.strip() for line in source_list.split('\n') if line.strip()]
        bibtex_output = ""

        for i, line in enumerate(lines):
            source_id = f"source{i+1}"
            clean_line = re.sub(r'^[\d\.\-\)\s]+', '', line).strip()

            url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+)', clean_line, re.IGNORECASE)
            url = url_match.group(1).rstrip('.,') if url_match else ""
            
            if url:
                clean_line = clean_line.replace(url_match.group(0), "").strip()
                clean_line = re.sub(r',?\s*Accessed\s+[A-Za-z0-9\s\,]+(?:$|,)', '', clean_line, flags=re.IGNORECASE).strip()

            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""
            clean_line = clean_line.rstrip(',. ')

            if ' v ' in clean_line.lower() or ' v. ' in clean_line.lower():
                entry_type = "jurisdiction"
            elif "'" in clean_line or '"' in clean_line:
                clean_line = clean_line.replace("'", "").replace('"', '')
                entry_type = "article"
            else:
                entry_type = "book"

            bibtex_entry = f"@{entry_type}{{{source_id},\n  title = {{{clean_line}}},\n  year = {{{year}}}"
            if url:
                bibtex_entry += f",\n  url = {{{url}}}"
            bibtex_entry += "\n}\n\n"
            bibtex_output += bibtex_entry

        return bibtex_output

# ==========================================
# 2. THE OSCOLA ENGINE (Backend)
# ==========================================
class LexiCiteEngine:
    def __init__(self, csl_url="https://raw.githubusercontent.com/citation-style-language/styles/master/oscola.csl"):
        self.csl_filename = "oscola.csl"
        self._ensure_csl(csl_url)

    def _ensure_csl(self, url):
        if not os.path.exists(self.csl_filename):
            urllib.request.urlretrieve(url, self.csl_filename)

    def _to_unicode_super(self, num_str):
        super_map = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹'}
        return "".join([super_map[char] for char in num_str])

    def format_document(self, docx_bytes, bibtex_data, num_sources):
        input_docx, md_file, bib_file, output_docx = "temp_in.docx", "temp.md", "library.bib", "LexiCite_Formatted.docx"
        try:
            with open(bib_file, "w", encoding="utf-8") as f: f.write(bibtex_data)
            with open(input_docx, "wb") as f: f.write(docx_bytes)

            subprocess.run(["pandoc", input_docx, "-t", "markdown", "-o", md_file], check=True)
            with open(md_file, "r", encoding="utf-8") as f: md_text = f.read()

            sorted_nums = sorted([str(i) for i in range(1, num_sources + 1)], key=len, reverse=True)
            footnote_appendix = "\n\n"

            for num in sorted_nums:
                marker = f"[^{num}]"
                md_text = md_text.replace(self._to_unicode_super(num), marker)
                md_text = re.sub(r'\\?\[\s*' + num + r'\s*\\?\]', marker, md_text)
                md_text = re.sub(r'\(\s*' + num + r'\s*\)', marker, md_text)
                md_text = re.sub(r'\^\s*' + num + r'\s*\^', marker, md_text)
                footnote_appendix += f"[^{num}]: [@source{num}]\n\n"

            md_text += footnote_appendix
            with open(md_file, "w", encoding="utf-8") as f: f.write(md_text)

            subprocess.run(["pandoc", md_file, "--citeproc", f"--bibliography={bib_file}", f"--csl={self.csl_filename}", "-M", "suppress-bibliography=true", "-o", output_docx], check=True)
            return output_docx
        finally:
            for f in [input_docx, md_file, bib_file]: 
                if os.path.exists(f): os.remove(f)

# ==========================================
# 3. THE FRONTEND UI & UX
# ==========================================
st.set_page_config(page_title="LexiCite Engine", page_icon="⚖️", layout="wide")

# Theme-Aware Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    /* Clean up default Streamlit padding */
    .block-container { padding-top: 3rem; max-width: 1000px; }
    
    /* Dynamic gradient that looks gorgeous on dark and light mode */
    .main-title { 
        font-weight: 800; 
        font-size: 4rem; 
        letter-spacing: -0.03em;
        background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        margin-bottom: 2rem;
    }

    /* Modern Button Styling */
    .stButton>button[kind="primary"] { 
        font-weight: 700; 
        border-radius: 8px; 
        padding: 0.75rem 2rem;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(59, 130, 246, 0.3);
    }
    
    /* Responsive Logo for Desktop */
    .logo-container img {
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------
# Desktop/Mobile Native Header
# ------------------------------------------
col_logo, col_text = st.columns([1.5, 8.5])

with col_logo:
    st.markdown('<div class="logo-container">', unsafe_allow_html=True)
    if os.path.exists("LexiCite.png"):
        st.image("LexiCite.png", use_container_width=True)
    else:
        st.markdown("<h1 style='font-size: 4rem;'>⚖️</h1>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_text:
    st.markdown("<h1 class='main-title'>LexiCite</h1>", unsafe_allow_html=True)

st.write("---")

# ------------------------------------------
# Quick Guide
# ------------------------------------------
with st.expander("📖 How to use LexiCite", expanded=False):
    st.info("""
    **Step 1:** Draft your document in Word. Use bracketed numbers **[1]** or superscripts **¹** for your footnotes.  
    **Step 2:** Upload that Word document below.  
    **Step 3:** Paste your list of sources in the exact order they appear in your text.  
    **Step 4:** Click Compile! LexiCite will map the sources, apply OSCOLA rules, and format your document.
    """)

st.write("")

# ------------------------------------------
# Main Application Workspace
# ------------------------------------------
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 📄 1. Upload Draft")
        st.caption("Upload your Microsoft Word document (.docx) containing your unformatted text.")
        st.write("") # Spacer
        uploaded_file = st.file_uploader("Word Document", type=["docx"], label_visibility="collapsed")

with col2:
    with st.container(border=True):
        st.markdown("### 📚 2. Paste Sources")
        st.caption("Paste your list in order.")
        source_list = st.text_area("Numbered List", height=150, placeholder="1. Agbaje v Commissioner of Police (1969) 1 NMLR 137\n2. https://www.courtofappeal.gov.ng/History", label_visibility="collapsed")

st.write("")
st.write("")

# ------------------------------------------
# Generation Zone
# ------------------------------------------
col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

with col_center:
    if st.button("⚡ PARSE & COMPILE DOCUMENT", type="primary"):
        if not uploaded_file or not source_list.strip():
            st.error("⚠️ Please upload a document and paste your sources to proceed.")
        else:
            with st.status("Initializing Engine...", expanded=True) as status:
                try:
                    # 1. Parse Data
                    st.write("🔍 Parsing sources using heuristics...")
                    parser = LexiCiteParser()
                    bib_data = parser.generate_bibtex(source_list)
                    num_sources = len([l for l in source_list.split('\n') if l.strip()])

                    # 2. Format Document
                    st.write("⚙️ Formatting OSCOLA Footnotes & Cross-References...")
                    engine = LexiCiteEngine()
                    final_path = engine.format_document(uploaded_file.getbuffer(), bib_data, num_sources)
                    
                    status.update(label="Compilation Complete!", state="complete")
                    
                    # 3. Success UI
                    st.success("✅ Document formatted successfully!")
                    st.balloons()

                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="📥 DOWNLOAD FORMATTED .DOCX", 
                            data=f, 
                            file_name="LexiCite_Formatted.docx", 
                            use_container_width=True,
                            type="primary"
                        )
                        
                    with st.expander("🛠️ View System-Generated Data (For Debugging)"):
                        st.code(bib_data, language="bibtex")

                except Exception as e:
                    status.update(label="System Error Occurred", state="error", expanded=True)
                    st.error(f"Error: {e}")
