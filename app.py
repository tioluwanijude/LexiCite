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
        # No API key needed! The brain is now 100% local.
        pass

    def generate_bibtex(self, source_list):
        """
        Uses Regular Expressions to parse a human-readable list into BibTeX.
        """
        lines = [line.strip() for line in source_list.split('\n') if line.strip()]
        bibtex_output = ""

        for i, line in enumerate(lines):
            source_id = f"source{i+1}"

            # 1. Strip leading numbers or bullets (e.g., "1. ", "2) ", "- ")
            clean_line = re.sub(r'^[\d\.\-\)\s]+', '', line).strip()

            # 2. Extract the year (Looks for 4 digits inside () or [])
            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""

            # 3. Categorize based on legal keywords
            if ' v ' in clean_line.lower() or ' v. ' in clean_line.lower():
                # It is a Case
                bibtex_output += f"@jurisdiction{{{source_id},\n  title = {{{clean_line}}},\n  year = {{{year}}}\n}}\n\n"
            
            elif "'" in clean_line or '"' in clean_line:
                # It is likely an Article (OSCOLA puts article titles in quotes)
                # Strip the quotes for the title field so Pandoc doesn't double-quote them
                clean_title = clean_line.replace("'", "").replace('"', '')
                bibtex_output += f"@article{{{source_id},\n  title = {{{clean_title}}},\n  year = {{{year}}}\n}}\n\n"
            
            else:
                # Default to Book or General Source
                bibtex_output += f"@book{{{source_id},\n  title = {{{clean_line}}},\n  year = {{{year}}}\n}}\n\n"

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
# 3. THE FRONTEND UI
# ==========================================
st.set_page_config(page_title="LexiCite Engine", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .main-title { font-weight: 800; font-size: 3rem; background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .stButton>button[kind="primary"] { background: #1E3A8A; color: white; border-radius: 8px; width: 100%; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Header
col_logo, col_text = st.columns([1, 8])
with col_logo:
    if os.path.exists("LexiCite.jpg"):
        st.image("LexiCite.jpg", use_container_width=True)
with col_text:
    st.markdown("<div class='main-title'>LexiCite Engine</div>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; font-size: 1.1rem;'>The Offline OSCOLA Formatting Tool</p>", unsafe_allow_html=True)

st.write("---")

# Main Interface
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 📄 Step 1: Upload Draft")
        st.caption("Upload your Word document (.docx) with superscript numbers.")
        uploaded_file = st.file_uploader("Word Document", type=["docx"], label_visibility="collapsed")

with col2:
    with st.container(border=True):
        st.markdown("### 📚 Step 2: Paste Sources")
        st.caption("Paste your list in order. The local engine will parse them automatically.")
        source_list = st.text_area("Numbered List", height=150, placeholder="1. Agbaje v Commissioner of Police (1969) 1 NMLR 137\n2. Malemi E, The Nigerian Constitutional Law (2012)")

st.write("")

if st.button("⚡ PARSE & COMPILE DOCUMENT", type="primary"):
    if not uploaded_file or not source_list.strip():
        st.error("⚠️ Please upload a document and paste your sources.")
    else:
        with st.status("Initializing Local Engine...", expanded=True) as status:
            try:
                # 1. Parse Data Locally
                st.write("🔍 Parsing sources using local heuristics...")
                parser = LexiCiteParser()
                bib_data = parser.generate_bibtex(source_list)
                num_sources = len([l for l in source_list.split('\n') if l.strip()])

                # 2. Format Document
                st.write("⚙️ Formatting OSCOLA Footnotes...")
                engine = LexiCiteEngine()
                final_path = engine.format_document(uploaded_file.getbuffer(), bib_data, num_sources)
                
                status.update(label="Compilation Complete!", state="complete")
                st.balloons()

                with st.expander("View System-Generated BibTeX Data"):
                    st.code(bib_data, language="bibtex")

                with open(final_path, "rb") as f:
                    st.download_button("📥 Download Document", f, "LexiCite_Formatted.docx")
            except Exception as e:
                status.update(label="System Error Occurred", state="error", expanded=True)
                st.error(f"Error: {e}")
