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

    def process_sources(self, source_list):
        lines = [line.strip() for line in source_list.split('\n') if line.strip()]
        cleaned_footnotes = []
        bib_entries = []

        for line in lines:
            # 1. Strip leading numbering: "1: ", "[1] ", "¹ "
            clean_line = re.sub(r'^[\d\.\-\)\:\s¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', line).strip()

            # 2. NALT RULE (Pg 71): Omit titles, prefixes, and post-nominals
            nalt_titles = r'\b(Mr\.|Mrs\.|Dr\.|Dr|Prof\.|Professor|Hon\.|Honourable|Justice|Rev\.|Bishop|Alhaji|Hajiya|Chief|SAN|OFR|OON|GCON)\b\,?\s*'
            clean_line = re.sub(nalt_titles, '', clean_line, flags=re.IGNORECASE)

            # 3. NALT RULE (Pg 81): Exterminate Banned Latin Expressions
            banned_latin = r'\b(supra|infra|ante|contra|id\.|op\.?\s*cit\.?|loc\.?\s*cit\.?|passim|et\s*seq\.?)\b'
            clean_line = re.sub(banned_latin, '', clean_line, flags=re.IGNORECASE)

            # 4. NALT RULE (Pg 59 & 67): Punctuation & Acronyms
            clean_line = re.sub(r'\s+v\.?\s+', ' v ', clean_line, flags=re.IGNORECASE)
            # Scrubber for dotted acronyms (e.g., N.W.L.R. -> NWLR, J.M. -> JM)
            clean_line = re.sub(r'([A-Za-z])\.', r'\1', clean_line)

            # 5. NALT RULE (Pg 63): Section and Part abbreviations
            clean_line = re.sub(r'\bSections\b', 'ss', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bSection\b', 's', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bParts\b', 'pts', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'\bPart\b', 'pt', clean_line, flags=re.IGNORECASE)

            # 6. Clean URLs and Web Artifacts
            # Extract URL from markdown links [URL](URL) or <URL>
            clean_line = re.sub(r'\[\s*(https?://[^\s\]\>]+)\s*\]\(.*?\)', r'\1', clean_line)
            clean_line = re.sub(r'<\s*(https?://[^\s\>]+)\s*>', r'\1', clean_line)
            
            # Remove "accessed DD Month YYYY"
            clean_line = re.sub(r',?\s*accessed\s+\d{1,2}\s+[a-zA-Z]+\s+\d{4}\.?', '', clean_line, flags=re.IGNORECASE)

            # Clean trailing cross-reference artifacts from copy-paste (e.g., "(n 24).")
            # We keep the cross-reference in the footnote, but we need to track if it IS a cross reference for the bibliography.
            
            # 7. Final Polish
            clean_line = re.sub(r',\s*,', ',', clean_line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()
            # Strip trailing weird characters but leave valid punctuation
            clean_line = clean_line.rstrip('>[]')

            cleaned_footnotes.append(clean_line)

            # 8. BIBLIOGRAPHY FILTER
            # We do not want 'ibid' or short cross-references in the master bibliography
            is_ibid = clean_line.lower() in ['ibid', 'ibid.']
            is_cross_ref = bool(re.search(r'\(\s*n\s*\d+\s*\)\.?$', clean_line, flags=re.IGNORECASE))
            
            if not is_ibid and not is_cross_ref:
                # Ensure no exact duplicates in the bibliography
                if clean_line not in bib_entries:
                    bib_entries.append(clean_line)

        # Alphabetize Bibliography
        bib_entries.sort(key=lambda x: x.lower())
        
        return cleaned_footnotes, bib_entries

# ==========================================
# 2. THE NALT COMPILATION ENGINE (Backend)
# ==========================================
class LexiCiteEngine:
    def _to_unicode_super(self, num_str):
        super_map = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹'}
        return "".join([super_map[char] for char in num_str])

    def format_document(self, docx_bytes, cleaned_footnotes, bib_entries, generate_bib):
        input_docx, md_file, output_docx = "temp_in.docx", "temp.md", "LexiCite_NALT_Formatted.docx"
        try:
            with open(input_docx, "wb") as f: f.write(docx_bytes)

            # Convert uploaded docx to markdown to inject footnotes natively
            subprocess.run(["pandoc", input_docx, "-t", "markdown", "-o", md_file], check=True)
            with open(md_file, "r", encoding="utf-8") as f: md_text = f.read()

            num_sources = len(cleaned_footnotes)
            # Sort numbers in reverse order so replacing '10' happens before '1'
            sorted_nums = sorted([str(i) for i in range(1, num_sources + 1)], key=len, reverse=True)
            
            footnote_appendix = "\n\n"

            for num in sorted_nums:
                marker = f"[^{num}]"
                
                # --- STRICT MODE ---
                # 1. Match ONLY raw Unicode superscripts (e.g., ¹, ², ³)
                # We have completely removed support for [1], ^1^, and (1)
                md_text = md_text.replace(self._to_unicode_super(num), marker)
                
                # Fetch the correct scrubbed footnote text
                idx = int(num) - 1
                if idx < len(cleaned_footnotes):
                    footnote_text = cleaned_footnotes[idx]
                    footnote_appendix += f"[^{num}]: {footnote_text}\n\n"

            md_text += footnote_appendix
            
            # --- NALT BIBLIOGRAPHY GENERATION ---
            if generate_bib and bib_entries:
                md_text += "\n\n<br><br>\n\n# BIBLIOGRAPHY\n\n"
                for entry in bib_entries:
                    md_text += f"* {entry}\n\n"
                
            with open(md_file, "w", encoding="utf-8") as f: f.write(md_text)

            # Convert directly back to Docx. Citeproc is bypassed for pristine formatting.
            subprocess.run(["pandoc", md_file, "-o", output_docx], check=True)
            return output_docx
            
        finally:
            for f in [input_docx, md_file]: 
                if os.path.exists(f): os.remove(f)

# ==========================================
# 3. THE FRONTEND UI & UX
# ==========================================
st.set_page_config(page_title="LexiCite | NALT", page_icon="⚡", layout="wide")

# --- CLEANED LIQUID GLASS & DARK PREMIUM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500&family=Instrument+Serif:ital@0;1&display=swap');
    
    /* Global App Background */
    .stApp {
        background-color: #050505 !important;
        background-image: radial-gradient(circle at 50% 0%, rgba(255,255,255,0.04) 0%, transparent 70%);
    }
    
    /* Safe Typography Overrides */
    html, body, p, .stMarkdown, .stText { 
        font-family: 'Barlow', sans-serif !important; 
    }
    
    /* Instrument Serif Headings */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Instrument Serif', serif !important;
        font-style: italic !important;
        color: #FFFFFF !important;
        letter-spacing: -0.02em !important;
        font-weight: 400 !important;
    }

    /* LIQUID GLASS CONTAINERS */
    [data-testid="stVerticalBlockBorderWrapper"], .stTextArea textarea {
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

    /* Custom Header Styles with Glowing Glass Effect */
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
        line-height: 0.9;
        letter-spacing: -0.02em;
        margin-bottom: 1rem;
        user-select: none;
    }
    .brand-lexi { color: #FFFFFF; }
    .brand-cite {
        background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0px 0px 15px rgba(139, 92, 246, 0.5));
    }
    .brand-dot { color: #3B82F6; }
    
    .hero-subtitle {
        font-family: 'Barlow', sans-serif;
        font-size: 1.05rem;
        color: rgba(255, 255, 255, 0.6);
        max-width: 650px;
        margin: 0 auto;
        line-height: 1.8;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------
# HERO SECTION (Instructions Integrated)
# ------------------------------------------
st.markdown("""
<div class="hero-container">
    <div class="hero-badge">NALT Engine 2.0</div>
    <div class="hero-title"><span class="brand-lexi">Lexi</span><span class="brand-cite">Cite</span><span class="brand-dot">.</span></div>
    <div class="hero-subtitle">
        <b>1.</b> Draft in Word using true Unicode superscripts (<b>¹</b>, <b>²</b>, <b>³</b>) for footnotes.<br>
        <b>2.</b> Upload your <b>.docx</b> file and paste your raw numbered sources below.<br>
        <b>3.</b> Compile to automatically scrub syntax and format to strict <b>NALT</b> standards.
    </div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------
# WORKSPACE (Grid Layout)
# ------------------------------------------
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.markdown("### 01. The Draft")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem; color: rgba(255,255,255,0.6);'>Upload your unformatted document. Ensure footnotes use strict Unicode superscripts (¹).</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload", type=["docx"], label_visibility="collapsed")
        st.write("")
        generate_bib = st.checkbox("Append NALT Bibliography", value=True)

with col2:
    with st.container(border=True):
        st.markdown("### 02. The Sources")
        st.markdown("<p style='font-size: 0.9rem; margin-bottom: 1rem; color: rgba(255,255,255,0.6);'>Paste your numbered list.</p>", unsafe_allow_html=True)
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
                    st.write("🔍 Sanitizing syntax & generating bibliography...")
                    parser = LexiCiteParser()
                    cleaned_footnotes, bib_entries = parser.process_sources(source_list)

                    st.write("⚙️ Applying strict NALT formatting rules natively...")
                    engine = LexiCiteEngine()
                    final_path = engine.format_document(uploaded_file.getbuffer(), cleaned_footnotes, bib_entries, generate_bib)
                    
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
                        
                    with st.expander("View System Logs & Scrubbed Output"):
                        st.markdown("**Cleaned Footnotes Injected:**")
                        for idx, fn in enumerate(cleaned_footnotes):
                            st.write(f"[{idx+1}] {fn}")
                        if generate_bib:
                            st.markdown("---")
                            st.markdown("**Generated Bibliography:**")
                            for b in bib_entries:
                                st.write(f"- {b}")

                except Exception as e:
                    status.update(label="System Error", state="error", expanded=True)
                    st.error(f"Error: {e}")
