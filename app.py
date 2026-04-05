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

            # 2. NALT RULE (Pg 71): Omit titles, prefixes, and post-nominals
            nalt_titles = r'\b(Mr\.|Mrs\.|Dr\.|Dr|Prof\.|Professor|Hon\.|Honourable|Justice|Rev\.|Bishop|Alhaji|Hajiya|Chief|SAN|OFR|OON|GCON)\b\,?'
            clean_line = re.sub(nalt_titles, '', clean_line, flags=re.IGNORECASE)
            
            # 3. NALT RULE (Pg 81): Exterminate Banned Latin Expressions
            banned_latin = r'\b(supra|infra|ante|contra|id\.|op\.?\s*cit\.?|loc\.?\s*cit\.?|passim|et\s*seq\.?)\b'
            clean_line = re.sub(banned_latin, '', clean_line, flags=re.IGNORECASE)

            # 4. NALT RULE (Pg 59 & 67): No full stops in abbreviations & unpunctuated 'v'
            clean_line = re.sub(r'\s+v\.?\s+', ' v ', clean_line, flags=re.IGNORECASE)
            # Scrubber for dotted acronyms (e.g., N.W.L.R. -> NWLR)
            clean_line = re.sub(r'\b([A-Z])\.(?:[A-Z]\.)+', lambda m: m.group(0).replace('.', ''), clean_line)
            
            # 5. NALT RULE (Pg 63): Section and Part abbreviations
            clean_line = re.sub(r'\bSections\b', 'ss', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bSection\b', 's', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bParts\b', 'pts', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bPart\b', 'pt', clean_line, flags=re.IGNORECASE)

            # Cleanup double spaces or stray commas left by scrubbers
            clean_line = re.sub(r',\s*,', ',', clean_line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()

            # 6. Extract URL
            url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+)', clean_line, re.IGNORECASE)
            url = url_match.group(1).rstrip('.,') if url_match else ""
            
            if url:
                clean_line = clean_line.replace(url_match.group(0), "").strip()
                clean_line = re.sub(r',?\s*Accessed\s+[A-Za-z0-9\s\,]+(?:$|,)', '', clean_line, flags=re.IGNORECASE).strip()

            # 7. Extract Year
            year_match = re.search(r'[\(\[](\d{4})[\)\]]', clean_line)
            year = year_match.group(1) if year_match else ""
            clean_line = clean_line.rstrip(',. ')

            # 8. NALT CATEGORIZATION ENGINE
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

            # 9. Build BibTeX
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
            
            # --- NALT BIBLIOGRAPHY GENERATION ---
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
st.set_page_config(page_title="LexiCite | NALT Engine", page_icon="LexiCite.png", layout="wide")

# Theme-Aware Styling inspired by Fintech Dashboards (Stripe/Linear)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        color: #475569; 
    }
    
    /* Typography Overrides */
    h1, h2, h3, h4, h5, h6, .markdown-text-container h1, .markdown-text-container h2, .markdown-text-container h3 {
        font-weight: 800 !important;
        letter-spacing: -0.04em !important;
        color: #0F172A !important;
    }
    
    p, .markdown-text-container p {
        font-weight: 400;
        line-height: 1.6;
        color: #475569;
    }
    
    .block-container { padding-top: 2rem; max-width: 1000px; }

    /* Custom Flexbox Header */
    .custom-header {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 15vh;
        margin-bottom: 3rem;
    }
    
    .brand-logo {
        font-weight: 800; 
        font-size: 4rem; 
        letter-spacing: -0.05em; 
        margin: 0;
        line-height: 1;
        user-select: none; 
    }
    
    .brand-lexi { color: #0F172A; }
    .brand-cite { color: #2563EB; }
    
    .header-subtitle {
        color: #64748B;
        font-size: 1.1rem;
        font-weight: 500;
        margin-top: 0.5rem;
    }

    /* Container Styling */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        background-color: #FFFFFF;
    }

    /* Primary Compile Button */
    .stButton>button[kind="primary"] { 
        border-radius: 9999px !important; 
        background-color: #2563EB !important;
        color: white !important;
        font-weight: 600 !important; 
        padding: 0.75rem 2.5rem !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        border: none !important;
        width: 100%;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 15px rgba(37, 99, 235, 0.3) !important;
        background-color: #1D4ED8 !important;
    }

    /* Download Button (Outlined Pill) */
    .stDownloadButton>button {
        border-radius: 9999px !important;
        border: 2px solid #2563EB !important;
        color: #2563EB !important;
        background-color: transparent !important;
        font-weight: 600 !important;
        width: 100% !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 0.75rem 2rem !important;
    }
    .stDownloadButton>button:hover {
        background-color: #EFF6FF !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15) !important;
    }
    
    /* Hide default uploader icon/text for sleekness */
    [data-testid="stFileUploadDropzone"] {
        border-radius: 8px !important;
        border: 1px dashed #CBD5E1 !important;
        background-color: #F8FAFC !important;
    }
</style>
""", unsafe_allow_html=True)

# 1. The Header (Top 15vh)
st.markdown("""
<div class="custom-header">
    <h1 class="brand-logo"><span class="brand-lexi">Lexi</span><span class="brand-cite">Cite</span></h1>
    <div class="header-subtitle">The NALT Engine for Legal Scholars.</div>
</div>
""", unsafe_allow_html=True)

# 2. The Workspace (Two Columns)
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 1. Upload Draft")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem;'>Upload your .docx file with bracketed [1] or superscript ¹ footnotes.</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload", type=["docx"], label_visibility="collapsed")
        st.write("")
        generate_bib = st.checkbox("Append NALT Bibliography to document", value=True)

with col2:
    with st.container(border=True):
        st.markdown("### 2. Paste Sources")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem;'>Paste your numbered list. The NALT engine will scrub and format them.</p>", unsafe_allow_html=True)
        source_list = st.text_area("Sources", height=300, placeholder="1. Prof. Abacha v. Fawehinmi [2000] FWLR (Pt 4) 533\n2. Electoral Act 2022\n3. https://www.courtofappeal.gov.ng/History", label_visibility="collapsed")

st.write("")
st.write("")

# 3. The Action Zone (Bottom Center)
col_empty1, col_center, col_empty2 = st.columns([1, 2, 1])

with col_center:
    if st.button("⚡ Parse & Compile", type="primary"):
        if not uploaded_file:
            st.error("⚠️ Please upload a Word document (.docx) to proceed.")
        elif not uploaded_file.name.endswith(".docx"):
            st.error("⚠️ Invalid file type. LexiCite only accepts .docx files.")
        elif uploaded_file.size > 50 * 1024 * 1024: 
            st.error("⚠️ File is too large. Please upload a document smaller than 50MB.")
        elif not source_list.strip():
            st.error("⚠️ Please paste your sources to proceed.")
        else:
            with st.status("Analyzing Jurisprudence...", expanded=True) as status:
                try:
                    st.write("🔍 Scrubbing titles, banned Latin, and classifying sources...")
                    parser = LexiCiteParser()
                    bib_data = parser.generate_bibtex(source_list)
                    num_sources = len([l for l in source_list.split('\n') if l.strip()])

                    st.write("⚙️ Applying NALT Formatting & Cross-References...")
                    engine = LexiCiteEngine()
                    final_path = engine.format_document(uploaded_file.getbuffer(), bib_data, num_sources, generate_bib)
                    
                    status.update(label="Compilation Complete!", state="complete")
                    
                    # Premium Micro-Interactions
                    st.balloons()
                    st.markdown("""
                        <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; color: #166534; padding: 1rem; border-radius: 12px; font-weight: 500; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                            <span style="font-size: 1.2rem;">✅</span> NALT Document formatted successfully!
                        </div>
                    """, unsafe_allow_html=True)

                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="Download Formatted .DOCX", 
                            data=f, 
                            file_name="LexiCite_NALT_Formatted.docx", 
                            use_container_width=True
                        )
                        
                    with st.expander("🛠️ View System-Generated Data (For Debugging)"):
                        st.code(bib_data, language="bibtex")

                except Exception as e:
                    status.update(label="System Error Occurred", state="error", expanded=True)
                    st.error(f"Error: {e}")
