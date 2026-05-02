'use strict';

const JSZip = require('jszip');

// ─────────────────────────────────────────────────────────────────
// NALT PARSER — port of Python LexiCiteParser
// ─────────────────────────────────────────────────────────────────
const STOP_WORDS = new Set(['v','and','of','the','for','in','on','at','to','a','an','de','la','vs','vs.']);
const ACRONYMS   = new Set(['qb','qbd','ac','er','hl','ca','nwlr','fwlr','sc','lpelr','uilr','llc','ukhl','nmlr','alr','npa','fcr','flr']);
const CAP_WORDS  = { ltd:'Ltd', co:'Co', plc:'Plc', inc:'Inc', all:'All', pt:'Pt', rep:'Rep', term:'Term', ex:'Ex', exch:'Exch' };

// Unicode superscript → digit
const SUPER_MAP = { '¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','⁰':'0' };

function smartFormatLegal(text) {
  return text.split(' ').map((w, i) => {
    if (!w) return '';
    const m = w.match(/^([\W_]*)([a-zA-Z0-9''\-]+)([\W_]*)$/);
    if (!m) return w;
    let [, pre, core, post] = m;
    const low = core.toLowerCase();
    if (STOP_WORDS.has(low))   core = i === 0 ? core[0].toUpperCase() + core.slice(1) : low;
    else if (ACRONYMS.has(low)) core = low.toUpperCase();
    else if (CAP_WORDS[low])    core = CAP_WORDS[low];
    else if (core === low || core === core.toUpperCase())
      core = core[0].toUpperCase() + core.slice(1);
    else
      core = core[0].toUpperCase() + core.slice(1);
    return pre + core + post;
  }).join(' ');
}

function extractUrl(text) {
  const m = text.match(/(https?:\/\/[a-zA-Z0-9.\-/?=&_%#~@:]+|www\.[a-zA-Z0-9.\-/?=&_%#~@:]+)/i);
  return m ? m[1] : '';
}

function processSource(rawLine) {
  // Strip leading list markers
  let c = rawLine.trim().replace(/^[\d.\-)\s]+/, '').trim();

  // NALT Pg 71: remove titles / post-nominals
  c = c.replace(/\b(Mr\.|Mrs\.|Dr\.?|Prof\.?|Professor|Hon\.|Honourable|Justice|Rev\.|Bishop|Alhaji|Hajiya|Chief|SAN|OFR|OON|GCON)\b,?/gi, '');

  // NALT Pg 81: ban Latin expressions
  c = c.replace(/\b(supra|infra|ante|contra|id\.|op\.?\s*cit\.?|loc\.?\s*cit\.?|passim|et\s*seq\.?)\b/gi, '');

  // NALT Pg 67: 'v.' → 'v'
  c = c.replace(/\s+v\.?\s+/gi, ' v ');

  // Undot acronyms: N.W.L.R. → NWLR
  c = c.replace(/\b([A-Z])\.(?:[A-Z]\.)+/g, m => m.replace(/\./g, ''));

  // NALT Pg 63: section/part abbreviations
  c = c.replace(/\bSections\b/gi, 'ss');
  c = c.replace(/\bSection\b/gi,  's');
  c = c.replace(/\bParts\b/gi,    'pts');
  c = c.replace(/\bPart\b/gi,     'pt');

  // Extract and strip URL
  const url = extractUrl(c);
  if (url) {
    c = c.replace(/\[(.*?)\]\(https?:\/\/[^)]+\)/gi, '$1');
    c = c.replace(/<\s*https?:\/\/[^>]+\s*>/gi, '');
    c = c.replace(/https?:\/\/\S+/gi, '');
    c = c.replace(/,?\s*[Aa]ccessed\s+[A-Za-z0-9\s,]+(?:$|,)/g, '');
  }

  // Clean cross-ref artifacts e.g. "(n 24)."
  c = c.replace(/\s*\(\s*n\s*\d+\s*\)\.?$/, '');

  // Tidy whitespace
  c = c.replace(/,\s*,/g, ',').replace(/\s+/g, ' ').trim();
  c = smartFormatLegal(c);

  // Extract year
  const yearM = c.match(/[([(\u005B](\d{4})[)\]\u005D]/);
  const year  = yearM ? yearM[1] : '';

  // Strip trailing punctuation
  c = c.replace(/[,. >\]'"]+$/, '').trim();

  // Categorise
  const lc = c.toLowerCase();
  let type;
  if      (/\s+v\s+|^re\s+|^ex\s+parte\s+/i.test(lc))             type = 'case';
  else if (/\b(act|law|decree|edict|constitution)\b/i.test(lc))    type = 'legislation';
  else if (/\bbill\b/i.test(lc))                                    type = 'bill';
  else if (/\b(report|law com|cmnd?)\b/i.test(lc))                 type = 'report';
  else if (/['\u2018\u2019\u201C\u201D"]/.test(c) || /\b(journal|review)\b/i.test(lc)) type = 'article';
  else if (url)                                                      type = 'webpage';
  else                                                               type = 'book';

  // OSCOLA-style formatted citation text
  let formatted = c;
  if (type === 'article') formatted = formatted.replace(/^['"'""]|['"'""]$/g, '');
  if (url && year) formatted += ` (${year})`;

  return { formatted, type, url, year };
}

// ─────────────────────────────────────────────────────────────────
// XML HELPERS
// ─────────────────────────────────────────────────────────────────
function escXml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&apos;');
}

function buildFootnotesXml(sources) {
  const entries = sources.map((src, i) => {
    const id  = i + 1;
    const txt = escXml(src.formatted) + (src.url ? ` &lt;${escXml(src.url)}&gt;` : '');
    return `  <w:footnote w:id="${id}">
    <w:p>
      <w:pPr><w:pStyle w:val="Footnote Text"/></w:pPr>
      <w:r>
        <w:rPr><w:rStyle w:val="Footnote Reference"/></w:rPr>
        <w:footnoteRef/>
      </w:r>
      <w:r><w:t xml:space="preserve"> ${txt}</w:t></w:r>
    </w:p>
  </w:footnote>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes
  xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
  mc:Ignorable="w14 w15">
  <w:footnote w:type="separator" w:id="-1">
    <w:p><w:r><w:separator/></w:r></w:p>
  </w:footnote>
  <w:footnote w:type="continuationSeparator" w:id="0">
    <w:p><w:r><w:continuationSeparator/></w:r></w:p>
  </w:footnote>
${entries}
</w:footnotes>`;
}

// Build bibliography paragraphs XML to append to document body
function buildBibliographyXml(sources) {
  const cases       = sources.filter(s => s.type === 'case');
  const legislation = sources.filter(s => s.type === 'legislation' || s.type === 'bill');
  const others      = sources.filter(s => !['case','legislation','bill'].includes(s.type));

  function section(title, items) {
    if (!items.length) return '';
    const heading = `  <w:p>
    <w:pPr>
      <w:pStyle w:val="Heading2"/>
      <w:spacing w:before="480" w:after="120"/>
    </w:pPr>
    <w:r><w:t>${escXml(title)}</w:t></w:r>
  </w:p>`;
    const rows = items.map(s =>
      `  <w:p>
    <w:pPr><w:ind w:left="720" w:hanging="720"/></w:pPr>
    <w:r><w:t xml:space="preserve">${escXml(s.formatted)}${s.url ? ' <' + escXml(s.url) + '>' : ''}</w:t></w:r>
  </w:p>`
    ).join('\n');
    return heading + '\n' + rows;
  }

  const divider = `  <w:p>
    <w:pPr><w:spacing w:before="480" w:after="0"/></w:pPr>
    <w:r/>
  </w:p>`;

  return `
  <w:p>
    <w:pPr><w:pageBreakBefore/></w:pPr>
    <w:r/>
  </w:p>
  <w:p>
    <w:pPr>
      <w:pStyle w:val="Heading1"/>
      <w:spacing w:before="0" w:after="240"/>
    </w:pPr>
    <w:r><w:t>Bibliography</w:t></w:r>
  </w:p>
${cases.length       ? section('Table of Cases', cases)       + divider : ''}
${legislation.length ? section('Table of Legislation', legislation) + divider : ''}
${others.length      ? section('Other Sources', others)        : ''}`;
}

// ─────────────────────────────────────────────────────────────────
// DOCUMENT XML PROCESSING — replace inline markers with footnote refs
// ─────────────────────────────────────────────────────────────────
function replaceMarkersInDocXml(xml, numSources) {
  // We process the XML one <w:r>…</w:r> block at a time.
  // Inside each run we look for:
  //   1. [N] bracket markers
  //   2. Unicode superscript digits (¹²³…)
  //   3. Runs with <w:vertAlign w:val="superscript"/> containing a bare digit

  // Helper: turn one run into footnote ref + optional surrounding text runs
  function processRun(runXml) {
    // Extract rPr block (optional)
    const rPrMatch = runXml.match(/<w:rPr>([\s\S]*?)<\/w:rPr>/);
    const rPrInner = rPrMatch ? rPrMatch[1] : null;
    const hasSuperAlign = rPrInner && /w:val="superscript"/.test(rPrInner);

    // Extract <w:t> content
    const tMatch = runXml.match(/<w:t(?:\s[^>]*)?>([^<]*)<\/w:t>/);
    if (!tMatch) return runXml; // No text, pass through (e.g. images)
    const rawText = tMatch[1];

    // Build a list of { start, end, num } for every marker found
    const hits = [];

    // [N] style
    let m;
    const bracketRe = /\[(\d+)\]/g;
    while ((m = bracketRe.exec(rawText)) !== null) {
      const num = parseInt(m[1], 10);
      if (num >= 1 && num <= numSources) {
        hits.push({ start: m.index, end: m.index + m[0].length, num });
      }
    }

    // Unicode superscripts (one char at a time)
    for (let i = 0; i < rawText.length; i++) {
      if (SUPER_MAP[rawText[i]]) {
        const num = parseInt(SUPER_MAP[rawText[i]], 10);
        if (num >= 1 && num <= numSources) {
          // Avoid double-counting if [N] already consumed this char
          const already = hits.some(h => h.start <= i && i < h.end);
          if (!already) hits.push({ start: i, end: i + 1, num });
        }
      }
    }

    // Bare digit in a superscript-styled run (e.g. <w:vertAlign val="superscript"/>)
    if (hasSuperAlign && /^\d+$/.test(rawText.trim())) {
      const num = parseInt(rawText.trim(), 10);
      if (num >= 1 && num <= numSources && hits.length === 0) {
        hits.push({ start: 0, end: rawText.length, num });
      }
    }

    if (hits.length === 0) return runXml;

    // Sort by start position
    hits.sort((a, b) => a.start - b.start);

    const footnoteRef = (num) =>
      `<w:r><w:rPr><w:rStyle w:val="Footnote Reference"/></w:rPr><w:footnoteReference w:id="${num}"/></w:r>`;
    const textRun = (txt) => txt
      ? `<w:r>${rPrMatch ? `<w:rPr>${rPrInner}</w:rPr>` : ''}<w:t xml:space="preserve">${escXml(txt)}</w:t></w:r>`
      : '';

    let out  = '';
    let last = 0;
    for (const h of hits) {
      out += textRun(rawText.slice(last, h.start));
      out += footnoteRef(h.num);
      last = h.end;
    }
    out += textRun(rawText.slice(last));
    return out;
  }

  // Replace all <w:r>…</w:r> blocks (non-greedy, handles nested rPr)
  return xml.replace(/<w:r>([\s\S]*?)<\/w:r>/g, (whole) => processRun(whole));
}

// ─────────────────────────────────────────────────────────────────
// RELATIONSHIP / CONTENT-TYPE HELPERS
// ─────────────────────────────────────────────────────────────────
function ensureFootnotesRelationship(relsXml) {
  if (/footnotes\.xml/i.test(relsXml)) return relsXml; // already there
  const fnType = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes';
  // Find highest existing rId number
  let maxId = 0;
  const idRe = /Id="rId(\d+)"/gi;
  let match;
  while ((match = idRe.exec(relsXml)) !== null) {
    maxId = Math.max(maxId, parseInt(match[1], 10));
  }
  const newRid = `rId${maxId + 1}`;
  const newRel = `<Relationship Id="${newRid}" Type="${fnType}" Target="footnotes.xml"/>`;
  return relsXml.replace('</Relationships>', `  ${newRel}\n</Relationships>`);
}

function ensureFootnotesContentType(ctXml) {
  const target = '/word/footnotes.xml';
  if (ctXml.includes(target)) return ctXml;
  const ct = 'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml';
  const override = `<Override PartName="${target}" ContentType="${ct}"/>`;
  return ctXml.replace('</Types>', `  ${override}\n</Types>`);
}

// ─────────────────────────────────────────────────────────────────
// LAMBDA HANDLER
// ─────────────────────────────────────────────────────────────────
exports.handler = async (event) => {
  const CORS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS, body: '' };
  }
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: CORS, body: 'Method Not Allowed' };
  }

  try {
    const body = JSON.parse(event.isBase64Encoded
      ? Buffer.from(event.body, 'base64').toString('utf8')
      : event.body);

    const { docxBase64, sources, generateBib } = body;
    if (!docxBase64 || !sources) {
      return { statusCode: 400, headers: { ...CORS, 'Content-Type': 'application/json' },
               body: JSON.stringify({ error: 'Missing docxBase64 or sources' }) };
    }

    // Parse sources
    const lines = sources.split('\n').filter(l => l.trim());
    if (!lines.length) {
      return { statusCode: 400, headers: { ...CORS, 'Content-Type': 'application/json' },
               body: JSON.stringify({ error: 'No sources found' }) };
    }
    const processed = lines.map(processSource);

    // Load the docx as a ZIP
    const docxBuf = Buffer.from(docxBase64, 'base64');
    const zip     = await JSZip.loadAsync(docxBuf);

    // ── document.xml ──────────────────────────────────────────────
    let docXml = await zip.file('word/document.xml').async('text');

    // Replace inline markers with proper w:footnoteReference elements
    docXml = replaceMarkersInDocXml(docXml, processed.length);

    // Optionally append bibliography before closing </w:body>
    if (generateBib) {
      const bibXml = buildBibliographyXml(processed);
      docXml = docXml.replace(/<\/w:body>/, bibXml + '\n</w:body>');
    }
    zip.file('word/document.xml', docXml);

    // ── footnotes.xml ─────────────────────────────────────────────
    zip.file('word/footnotes.xml', buildFootnotesXml(processed));

    // ── relationships ─────────────────────────────────────────────
    const relsPath = 'word/_rels/document.xml.rels';
    if (zip.file(relsPath)) {
      let relsXml = await zip.file(relsPath).async('text');
      relsXml = ensureFootnotesRelationship(relsXml);
      zip.file(relsPath, relsXml);
    }

    // ── content types ─────────────────────────────────────────────
    const ctPath = '[Content_Types].xml';
    if (zip.file(ctPath)) {
      let ctXml = await zip.file(ctPath).async('text');
      ctXml = ensureFootnotesContentType(ctXml);
      zip.file(ctPath, ctXml);
    }

    // ── output ────────────────────────────────────────────────────
    const outBuf = await zip.generateAsync({
      type:               'nodebuffer',
      compression:        'DEFLATE',
      compressionOptions: { level: 6 },
    });

    return {
      statusCode: 200,
      headers: { ...CORS, 'Content-Type': 'application/json' },
      body: JSON.stringify({ docxBase64: outBuf.toString('base64') }),
    };

  } catch (err) {
    console.error('LexiCite error:', err);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: err.message || 'Internal server error' }),
    };
  }
};
