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
        # 100% Local, Offline Engine. No APIs required.
        pass

    def generate_bibtex(self, source_list):
        """
        Uses Advanced Regular Expressions to parse human-readable lists into valid BibTeX.
        """
        lines = [line.strip() for line in source_list.split('\n') if line.strip()]
        bibtex_output = ""

        for i, line in enumerate(lines):
            source_id = f"source{i+1}"

            # 1. Strip leading numbers or bullets (e.g., "1. ", "2) ", "- ")
            clean_line = re.sub(r'^[\d\.\-\)\s]+', '', line).strip()

            # 2. Extract the URL (OSCOLA strict compliance)
            url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+)', clean_line, re.IGNORECASE)
            url = url_match.group(1).rstrip('.,') if url_match else ""
            
            if url:
                # Remove the URL from the main title string
                clean_line = clean_line.replace(url_match.group(0), "").strip()
                # Clean up stray 'Accessed' words left behind by raw copy/pasting
                clean_line = re.sub(r',?\s*Accessed\s+[A-Za-z0-9\s\,]+(?:$|,)', '', clean_line, flags=re.IGNORECASE).strip()

            # 3. Extract the year (Looks for 4 digits inside () or [])
            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""

            # Clean trailing punctuation from the title
            clean_line = clean_line.rstrip(',. ')

            # 4. Categorize based on legal keywords
            if ' v ' in clean_line.lower() or ' v. ' in clean_line.lower():
                entry_type = "jurisdiction"
                
            elif "'" in clean_line or '"' in clean_line:
                # It is likely an Article. Strip the quotes so Pandoc doesn't double-quote them.
                clean_line = clean_line.replace("'", "").replace('"', '')
                entry_type = "article"
                
            else:
                entry_type = "book"

            # 5. Build the BibTeX Entry
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
        """Downloads the official OSCOLA ruleset if missing."""
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
                # Find all variations of footnotes and normalize them to markdown footnotes
                md_text = md_text.replace(self._to_unicode_super(num), marker)
                md_text = re.sub(r'\\?\[\s*' + num + r'\s*\\?\]', marker, md_text)
                md_text = re.sub(r'\(\s*' + num + r'\s*\)', marker, md_text)
                md_text = re.sub(r'\^\s*' + num + r'\s*\^', marker, md_text)
                
                # Append the mapping link to the bottom of the document
                footnote_appendix += f"[^{num}]: [@source{num}]\n\n"

            md_text += footnote_appendix
            with open(md_file, "w", encoding="utf-8") as f: f.write(md_text)

            # Fire the Pandoc CSL processor
            subprocess.run(["pandoc", md_file, "--citeproc", f"--bibliography={bib_file}", f"--csl={self.csl_filename}", "-M", "suppress-bibliography=true", "-o", output_docx], check=True)
            return output_docx
        finally:
            for f in [input_docx, md_file, bib_file]: 
                if os.path.exists(f): os.remove(f)

# ==========================================
# 3. THE FRONTEND UI & UX
# ==========================================
st.set_page_config(page_title="LexiCite | OSCOLA Engine", page_icon="⚖️", layout="wide")

# Modern UI Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main-title { 
        font-weight: 800; 
        font-size: 3.2rem; 
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #0F172A 0%, #3B82F6 100%); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        margin-bottom: 0px;
    }
    
    .stButton>button[kind="primary"] { 
        background: #0F172A; 
        color: white; 
        border-radius: 8px; 
        width: 100%; 
        font-weight: 600; 
        padding: 0.75rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .stButton>button[kind="primary"]:hover {
        background: #1E293B;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    .info-box {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header Section
col_logo, col_text = st.columns([1, 9])
with col_logo:
    if os.path.exists("LexiCite.jpg"):
        st.image("LexiCite.jpg", use_container_width=True)
    else:
        st.markdown("<h1 style='font-size: 3rem;'>⚖️</h1>", unsafe_allow_html=True)

with col_text:
    st.markdown("<div class='main-title'>LexiCite OSCOLA Engine</div>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; font-size: 1.1rem; font-weight: 500;'>The 100% Offline, Privacy-First Legal Formatting Tool</p>", unsafe_allow_html=True)

st.write("---")

# Quick Guide
with st.expander("📖 How to use LexiCite"):
    st.markdown("""
    <div class='info-box'>
        <strong>Step 1:</strong> Type your draft in Word and use numbers in brackets <b>[1]</b> or superscripts <b>¹</b> for your footnotes.<br>
        <strong>Step 2:</strong> Upload that Word document here.<br>
        <strong>Step 3:</strong> Paste your list of sources in the exact order they appear in your text.<br>
        <strong>Step 4:</strong> Click Compile. LexiCite will map the sources, apply strict OSCOLA rules, and generate a formatted document.
    </div>
    """, unsafe_allow_html=True)

# Main Application Workspace
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 📄 1. Upload Draft")
        st.caption("Upload your Microsoft Word document (.docx) containing your unformatted text.")
        uploaded_file = st.file_uploader("Word Document", type=["docx"], label_visibility="collapsed")

with col2:
    with st.container(border=True):
        st.markdown("### 📚 2. Paste Sources")
        st.caption("Paste your list in order. Ensure cases have 'v' and web sources include the URL.")
        source_list = st.text_area("Numbered List", height=150, placeholder="1. Agbaje v Commissioner of Police (1969) 1 NMLR 137\n2. https://www.courtofappeal.gov.ng/History")

st.write("")
st.write("")

# Generation Zone
col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

with col_center:
    if st.button("⚡ PARSE & COMPILE DOCUMENT", type="primary"):
        if not uploaded_file or not source_list.strip():
            st.error("⚠️ Please upload a document and paste your sources to proceed.")
        else:
            with st.status("Initializing Local Engine...", expanded=True) as status:
                try:
                    # 1. Parse Data Locally
                    st.write("🔍 Parsing sources using local heuristics...")
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

                    # Provide Download Button Prominently
                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="📥 DOWNLOAD FORMATTED .DOCX", 
                            data=f, 
                            file_name="LexiCite_Formatted.docx", 
                            use_container_width=True,
                            type="primary"
                        )
                        
                    # Developer tools hidden in expander
                    with st.expander("🛠️ View System-Generated Data (For Debugging)"):
                        st.code(bib_data, language="bibtex")

                except Exception as e:
                    status.update(label="System Error Occurred", state="error", expanded=True)
                    st.error(f"Error: {e}")
