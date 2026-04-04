import streamlit as st
import os
import subprocess
import urllib.request
import re

# ==========================================
# 1. THE NALT HEURISTIC PARSER (Backend)
# ==========================================
class LexiCiteParser:
    def __init__(self):
        pass

    def generate_bibtex(self, source_list):
        lines = [line.strip() for line in source_list.split('\n') if line.strip()]
        bibtex_output = ""

        for i, line in enumerate(lines):
            source_id = f"source{i+1}"
            
            # 1. Strip leading numbers/bullets
            clean_line = re.sub(r'^[\d\.\-\)\s]+', '', line).strip()

            # 2. NALT RULE: Omit titles, prefixes, and post-nominals (Page 71 NALT Guide)
            nalt_titles = r'\b(Mr\.|Mrs\.|Dr\.|Dr|Prof\.|Professor|Hon\.|Honourable|Justice|Rev\.|Bishop|Alhaji|Hajiya|Chief|SAN|OFR|OON|GCON)\b\,?'
            clean_line = re.sub(nalt_titles, '', clean_line, flags=re.IGNORECASE)
            
            # 3. NALT RULE: No full stops in abbreviations / unpunctuated 'v' (Page 59 & 67 NALT Guide)
            clean_line = re.sub(r'\s+v\.?\s+', ' v ', clean_line, flags=re.IGNORECASE)
            
            # Cleanup double spaces or stray commas left by title stripping
            clean_line = re.sub(r',\s*,', ',', clean_line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()

            # 4. Extract URL
            url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+)', clean_line, re.IGNORECASE)
            url = url_match.group(1).rstrip('.,') if url_match else ""
            
            if url:
                clean_line = clean_line.replace(url_match.group(0), "").strip()
                clean_line = re.sub(r',?\s*Accessed\s+[A-Za-z0-9\s\,]+(?:$|,)', '', clean_line, flags=re.IGNORECASE).strip()

            # 5. Extract Year
            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""
            clean_line = clean_line.rstrip(',. ')

            # 6. NALT CATEGORIZATION ENGINE
            clean_lower = clean_line.lower()
            
            if re.search(r'\s+v\s+|^re\s+|^ex\s+parte\s+', clean_lower):
                entry_type = "jurisdiction"
            elif re.search(r'\b(act|law|decree|edict|constitution)\b', clean_lower):
                entry_type = "legislation"
            elif re.search(r'\bbill\b', clean_lower):
                entry_type = "bill"
            elif re.search(r'\b(report|law com|cmnd?)\b', clean_lower):
                entry_type = "report"
            elif "'" in clean_line or '"' in clean_line or re.search(r'\b(journal|review)\b', clean_lower):
                clean_line = clean_line.replace("'", "").replace('"', '') 
                entry_type = "article"
            elif url:
                entry_type = "webpage"
            else:
                entry_type = "book"

            # 7. Build BibTeX
            bibtex_entry = f"@{entry_type}{{{source_id},\n  title = {{{clean_line}}},\n  year = {{{year}}}"
            if url:
                bibtex_entry += f",\n  url = {{{url}}}"
            bibtex_entry += "\n}\n\n"
            
            bibtex_output += bibtex_entry

        return bibtex_output

# ==========================================
# 2. THE NALT COMPILATION ENGINE (Backend)
# ==========================================
class LexiCiteEngine:
    def __init__(self, csl_url="https://raw.githubusercontent.com/citation-style-language/styles/master/oscola.csl"):
        # NALT utilizes OSCOLA mechanics for formatting and cross-referencing.
        self.csl_filename = "nalt_core.csl"
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
st.set_page_config(page_title="LexiCite | NALT Engine", page_icon="LexiCite.png", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    .block-container { padding-top: 2.5rem; max-width: 1000px; }

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
    
    .brand-logo {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 900; 
        font-size: 4.5rem; 
        letter-spacing: -0.05em; 
        margin: 0;
        margin-bottom: 2.5rem;
        user-select: none; 
    }
    
    .brand-lexi { color: inherit; }
    
    .brand-cite {
        background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .brand-dot { color: #3B82F6; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="brand-logo"><span class="brand-lexi">Lexi</span><span class="brand-cite">Cite</span><span class="brand-dot">.</span></h1>', unsafe_allow_html=True)

with st.expander("📖 How to use the LexiCite NALT Engine", expanded=False):
    st.info("""
    **Step 1:** Draft your document in Word. Use bracketed numbers **[1]** or superscripts **¹** for your footnotes.  
    **Step 2:** Upload your draft below.  
    **Step 3:** Paste your list of sources.  
    **Step 4:** Click Compile! LexiCite will scrub titles (e.g., Prof., SAN), normalize your citations, and apply the official NALT formatting rules.
    """)

col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 📄 1. Upload Draft")
        st.write("")
        uploaded_file = st.file_uploader("Word Document", type=["docx"], label_visibility="collapsed")

with col2:
    with st.container(border=True):
        st.markdown("### 📚 2. Paste Sources")
        source_list = st.text_area("Numbered List", height=150, placeholder="1. Prof. Abacha v. Fawehinmi [2000] FWLR (Pt 4) 533\n2. Electoral Act 2022\n3. https://www.courtofappeal.gov.ng/History", label_visibility="collapsed")

st.write("")
st.write("")

col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

with col_center:
    if st.button("⚡ PARSE & COMPILE NALT DOCUMENT", type="primary"):
        if not uploaded_file:
            st.error("⚠️ Please upload a Word document (.docx) to proceed.")
        elif not uploaded_file.name.endswith(".docx"):
            st.error("⚠️ Invalid file type. LexiCite only accepts .docx files.")
        elif uploaded_file.size > 50 * 1024 * 1024: 
            st.error("⚠️ File is too large. Please upload a document smaller than 50MB.")
        elif not source_list.strip():
            st.error("⚠️ Please paste your sources to proceed.")
        else:
            with st.status("Initializing NALT Engine...", expanded=True) as status:
                try:
                    st.write("🔍 Scrubbing titles, punctuation, and classifying sources...")
                    parser = LexiCiteParser()
                    bib_data = parser.generate_bibtex(source_list)
                    num_sources = len([l for l in source_list.split('\n') if l.strip()])

                    st.write("⚙️ Applying NALT Formatting & Cross-References...")
                    engine = LexiCiteEngine()
                    final_path = engine.format_document(uploaded_file.getbuffer(), bib_data, num_sources)
                    
                    status.update(label="Compilation Complete!", state="complete")
                    
                    st.success("✅ NALT Document formatted successfully!")
                    st.balloons()

                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="📥 DOWNLOAD FORMATTED .DOCX", 
                            data=f, 
                            file_name="LexiCite_NALT_Formatted.docx", 
                            use_container_width=True,
                            type="primary"
                        )
                        
                    with st.expander("🛠️ View System-Generated Data (For Debugging)"):
                        st.code(bib_data, language="bibtex")

                except Exception as e:
                    status.update(label="System Error Occurred", state="error", expanded=True)
                    st.error(f"Error: {e}")
