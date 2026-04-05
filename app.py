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
            
            clean_line = re.sub(r'^[\d\.\-\)\s]+', '', line).strip()
            nalt_titles = r'\b(Mr\.|Mrs\.|Dr\.|Dr|Prof\.|Professor|Hon\.|Honourable|Justice|Rev\.|Bishop|Alhaji|Hajiya|Chief|SAN|OFR|OON|GCON)\b\,?'
            clean_line = re.sub(nalt_titles, '', clean_line, flags=re.IGNORECASE)
            
            banned_latin = r'\b(supra|infra|ante|contra|id\.|op\.?\s*cit\.?|loc\.?\s*cit\.?|passim|et\s*seq\.?)\b'
            clean_line = re.sub(banned_latin, '', clean_line, flags=re.IGNORECASE)

            clean_line = re.sub(r'\s+v\.?\s+', ' v ', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\b([A-Z])\.(?:[A-Z]\.)+', lambda m: m.group(0).replace('.', ''), clean_line)
            
            clean_line = re.sub(r'\bSections\b', 'ss', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bSection\b', 's', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bParts\b', 'pts', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bPart\b', 'pt', clean_line, flags=re.IGNORECASE)

            clean_line = re.sub(r',\s*,', ',', clean_line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()

            url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+)', clean_line, re.IGNORECASE)
            url = url_match.group(1).rstrip('.,') if url_match else ""
            
            if url:
                clean_line = clean_line.replace(url_match.group(0), "").strip()
                clean_line = re.sub(r',?\s*Accessed\s+[A-Za-z0-9\s\,]+(?:$|,)', '', clean_line, flags=re.IGNORECASE).strip()

            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""
            clean_line = clean_line.rstrip(',. ')

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
        self.csl_filename = "nalt_core.csl"
        self._ensure_csl(csl_url)

    def _ensure_csl(self, url):
        if not os.path.exists(self.csl_filename):
            urllib.request.urlretrieve(url, self.csl_filename)

    def _to_unicode_super(self, num_str):
        super_map = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹'}
        return "".join([super_map[char] for char in num_str])

    def format_document(self, docx_bytes, bibtex_data, num_sources, generate_bib):
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
            
            if generate_bib:
                md_text += "\n\n<br><br>\n\n# BIBLIOGRAPHY\n\n"
                
            with open(md_file, "w", encoding="utf-8") as f: f.write(md_text)

            cmd = ["pandoc", md_file, "--citeproc", f"--bibliography={bib_file}", f"--csl={self.csl_filename}"]
            if not generate_bib:
                cmd.extend(["-M", "suppress-bibliography=true"])
            cmd.extend(["-o", output_docx])
            
            subprocess.run(cmd, check=True)
            return output_docx
        finally:
            for f in [input_docx, md_file, bib_file]: 
                if os.path.exists(f): os.remove(f)

# ==========================================
# 3. THE FRONTEND UI & UX
# ==========================================
st.set_page_config(page_title="LexiCite | NALT", page_icon="⚡", layout="wide")

# --- LIQUID GLASS & DARK PREMIUM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500&family=Instrument+Serif:ital@0;1&display=swap');
    
    /* Global App Background */
    .stApp {
        background-color: #050505 !important;
        background-image: radial-gradient(circle at 50% 0%, rgba(255,255,255,0.05) 0%, transparent 70%);
    }
    
    html, body, [class*="css"], p, span, label { 
        font-family: 'Barlow', sans-serif !important; 
        color: rgba(255, 255, 255, 0.6) !important;
        font-weight: 300;
    }
    
    /* Instrument Serif Headings */
    h1, h2, h3, .markdown-text-container h1, .markdown-text-container h2, .markdown-text-container h3 {
        font-family: 'Instrument Serif', serif !important;
        font-style: italic !important;
        color: #FFFFFF !important;
        letter-spacing: -0.02em !important;
        font-weight: 400 !important;
    }

    /* LIQUID GLASS CONTAINERS */
    [data-testid="stVerticalBlockBorderWrapper"], .stTextArea textarea, [data-testid="stFileUploadDropzone"] {
        background: rgba(255, 255, 255, 0.02) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05) !important;
        color: #FFFFFF !important;
        transition: all 0.3s ease;
    }
    
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
    }

    /* LIQUID GLASS STRONG BUTTONS */
    .stButton>button[kind="primary"], .stDownloadButton>button { 
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(50px) !important;
        -webkit-backdrop-filter: blur(50px) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: #FFFFFF !important;
        border-radius: 9999px !important; 
        font-family: 'Barlow', sans-serif !important;
        font-weight: 500 !important;
        padding: 0.75rem 2.5rem !important;
        transition: all 0.4s ease !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.15), 0 4px 10px rgba(0,0,0,0.3) !important;
        width: 100%;
    }
    .stButton>button[kind="primary"]:hover, .stDownloadButton>button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        transform: translateY(-2px) !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.2), 0 0 20px rgba(255, 255, 255, 0.1) !important;
    }

    /* Hide redundant elements */
    header, footer { visibility: hidden !important; }
    .block-container { padding-top: 3rem; max-width: 1100px; }

    /* Custom Header Styles */
    .hero-container {
        text-align: center;
        margin-bottom: 4rem;
        padding-top: 2rem;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 255, 255, 0.8);
        margin-bottom: 1.5rem;
    }
    .hero-title {
        font-family: 'Instrument Serif', serif;
        font-style: italic;
        font-size: 5.5rem;
        color: #FFFFFF;
        line-height: 0.9;
        letter-spacing: -0.02em;
        margin-bottom: 1rem;
    }
    .hero-subtitle {
        font-family: 'Barlow', sans-serif;
        font-size: 1.1rem;
        color: rgba(255, 255, 255, 0.5);
        max-width: 500px;
        margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------
# HERO SECTION (Apple/Agency Inspired)
# ------------------------------------------
st.markdown("""
<div class="hero-container">
    <div class="hero-badge">NALT Engine 2.0</div>
    <div class="hero-title">LexiCite.</div>
    <div class="hero-subtitle">Pro features. Zero complexity. The aesthetic legal formatting engine built exclusively for Nigerian scholars.</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------
# WORKSPACE (Grid Layout)
# ------------------------------------------
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 01. The Draft")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem;'>Upload your unformatted .docx file. Ensure footnotes are marked with brackets [1] or superscripts ¹.</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload", type=["docx"], label_visibility="collapsed")
        st.write("")
        generate_bib = st.checkbox("Append NALT Bibliography", value=True)

with col2:
    with st.container(border=True):
        st.markdown("### 02. The Sources")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem;'>Paste your numbered list. Our engine automatically scrubs banned Latin and standardizes abbreviations.</p>", unsafe_allow_html=True)
        source_list = st.text_area("Sources", height=200, placeholder="1. Prof. Abacha v. Fawehinmi [2000] FWLR (Pt 4) 533\n2. Electoral Act 2022\n3. https://www.courtofappeal.gov.ng/History", label_visibility="collapsed")

st.write("")
st.write("")

# ------------------------------------------
# ACTION CTA
# ------------------------------------------
col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

with col_center:
    if st.button("Initialize Compilation", type="primary"):
        if not uploaded_file:
            st.error("⚠️ Please upload a Word document (.docx) to proceed.")
        elif not uploaded_file.name.endswith(".docx"):
            st.error("⚠️ Invalid file type. LexiCite only accepts .docx files.")
        elif uploaded_file.size > 50 * 1024 * 1024: 
            st.error("⚠️ File is too large. Please upload a document smaller than 50MB.")
        elif not source_list.strip():
            st.error("⚠️ Please paste your sources to proceed.")
        else:
            with st.status("Reconstructing Jurisprudence...", expanded=True) as status:
                try:
                    st.write("🔍 Sanitizing syntax & classifying sources...")
                    parser = LexiCiteParser()
                    bib_data = parser.generate_bibtex(source_list)
                    num_sources = len([l for l in source_list.split('\n') if l.strip()])

                    st.write("⚙️ Applying strict NALT formatting rules...")
                    engine = LexiCiteEngine()
                    final_path = engine.format_document(uploaded_file.getbuffer(), bib_data, num_sources, generate_bib)
                    
                    status.update(label="Compilation Complete.", state="complete")
                    
                    st.balloons()
                    st.markdown("""
                        <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 1rem; border-radius: 12px; text-align: center; margin-bottom: 1.5rem; backdrop-filter: blur(10px);">
                            <i>Document has been perfectly formatted to NALT standards.</i>
                        </div>
                    """, unsafe_allow_html=True)

                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="Download .DOCX", 
                            data=f, 
                            file_name="LexiCite_NALT_Formatted.docx", 
                            use_container_width=True
                        )
                        
                    with st.expander("View Backend Trace (BibTeX)"):
                        st.code(bib_data, language="bibtex")

                except Exception as e:
                    status.update(label="System Error", state="error", expanded=True)
                    st.error(f"Error: {e}")
