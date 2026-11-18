"""
Thème visuel BizStock : fond kaki / blanc sable, effet verre dépoli, bleu et orange du logo.
Les clés de TONES gardent leurs anciens noms (mint, lime, amber, coral, teal) mais portent
maintenant la palette BizStock : mint = vert (succès), lime = bleu logo, amber = orange logo,
coral = rouge (alerte/dette), teal = turquoise.
"""
import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

TONES = {
    "mint": "#1F9D6B",
    "lime": "#1565C0",
    "amber": "#F28C0F",
    "coral": "#D9433F",
    "teal": "#0E8A94",
}

CSS = """
<style>
/* Polices hébergées avec l'app (static/fonts) : aucune requête vers un service tiers (ex. Google Fonts). */
@font-face{font-family:'Outfit';src:url('app/static/fonts/outfit-latin-wght-normal.woff2') format('woff2');font-weight:100 900;font-style:normal;font-display:swap;}
@font-face{font-family:'JetBrains Mono';src:url('app/static/fonts/jetbrains-mono-latin-500-normal.woff2') format('woff2');font-weight:500;font-style:normal;font-display:swap;}
@font-face{font-family:'JetBrains Mono';src:url('app/static/fonts/jetbrains-mono-latin-700-normal.woff2') format('woff2');font-weight:700;font-style:normal;font-display:swap;}

@property --a{syntax:'<angle>';initial-value:0deg;inherits:false;}

:root{
  --ink:#0F2742; --mut:#5C6B7C; --blue:#1565C0; --navy:#0E3A66; --orange:#FF8A00;
  --green:#1F9D6B; --red:#D9433F;
  --glass:linear-gradient(135deg, rgba(255,255,255,.78), rgba(255,255,255,.42));
  --glass-line:rgba(255,255,255,.85);
  --shadow:0 1px 0 rgba(255,255,255,.95) inset, 0 18px 50px -20px rgba(14,58,102,.38);
}
html, body, .stApp, button, input, textarea, label, p, li, h1, h2, h3, h4{font-family:'Outfit',system-ui,sans-serif;}
.stApp{
  color:var(--ink);
  background:
    radial-gradient(1000px 620px at 0% -10%, rgba(21,101,192,.24), transparent 62%),
    radial-gradient(900px 620px at 100% 110%, rgba(255,138,0,.26), transparent 62%),
    radial-gradient(760px 520px at 86% 4%, rgba(160,154,98,.34), transparent 62%),
    radial-gradient(rgba(14,58,102,.11) 1.2px, transparent 1.5px),
    linear-gradient(160deg, #F6F2E6, #E4DEC6);
  background-size:auto, auto, auto, 24px 24px, auto;
  background-repeat:no-repeat, no-repeat, no-repeat, repeat, no-repeat;
  background-attachment:fixed;
  animation:drift 26s ease-in-out infinite alternate;
}
@keyframes drift{
  from{background-position:0 0, 100% 100%, 86% 0, 0 0, 0 0;}
  to{background-position:7% 5%, 93% 94%, 78% 9%, 0 0, 0 0;}
}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2rem;max-width:1180px;}
h1,h2,h3,h4{color:var(--ink);letter-spacing:-.02em;font-weight:700;}
hr{border-color:rgba(14,58,102,.14)!important;}

/* ---------- Verre dépoli ---------- */
.glass, .hero, .kpi, .row-card, .pay-card, .ring-card, .brand-card{
  background:var(--glass);backdrop-filter:blur(18px) saturate(165%);-webkit-backdrop-filter:blur(18px) saturate(165%);
  border:1px solid var(--glass-line);box-shadow:var(--shadow);
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"]{
  background:
    radial-gradient(420px 300px at 100% 100%, rgba(255,138,0,.38), transparent 70%),
    radial-gradient(380px 260px at 0% 0%, rgba(80,150,230,.35), transparent 70%),
    linear-gradient(190deg,#0E3A66 0%,#0A2C4F 55%,#071F3B 100%);
  border-right:1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#DCE8F5;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.16)!important;}
[data-testid="stSidebar"] div[role="radiogroup"]{gap:6px;}
[data-testid="stSidebar"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]){
  padding:11px 14px;border-radius:14px;border:1px solid transparent;width:100%;transition:all .22s;cursor:pointer;
}
[data-testid="stSidebar"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):hover{background:rgba(255,255,255,.09);transform:translateX(3px);}
[data-testid="stSidebar"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):has(input:checked){
  background:linear-gradient(90deg,#FF8A00,#FFA833);border-color:rgba(255,255,255,.4);
  box-shadow:0 10px 26px -10px rgba(255,138,0,.9);
}
[data-testid="stSidebar"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):has(input:checked) p{color:#fff;font-weight:700;}
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child{display:none;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]){display:none;}
[data-testid="stSidebar"] a{color:#9CC8FF!important;}
/* Zone de déconnexion : poussée tout en bas de la barre latérale (le parent flex est étiré, l'enveloppe passe en dernier) */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > .st-key-sidebar_logout),
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(> .st-key-sidebar_logout){min-height:calc(100vh - 6rem);}
[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_logout){order:99;margin-top:auto;}
.st-key-sidebar_logout{order:99;margin-top:auto;padding-top:14px;border-top:1px solid rgba(255,255,255,.16);}
[data-testid="stSidebar"] .pill{background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.35);}
.brand-card{border-radius:20px;padding:14px 16px 10px;text-align:center;margin-bottom:14px;background:rgba(255,255,255,.94)!important;}
.brand-card img{width:100%;max-width:170px;display:block;margin:0 auto;}
.brand-card .shop{margin-top:8px;font-weight:600;color:var(--navy);font-size:.9rem;word-break:break-word;}

/* ---------- Hero ---------- */
.hero{
  position:relative;display:flex;align-items:center;gap:22px;padding:24px 28px;border-radius:28px;margin-bottom:20px;
  animation:rise .6s both;
}
.hero::before{
  content:"";position:absolute;inset:0;border-radius:inherit;padding:2px;pointer-events:none;
  background:conic-gradient(from var(--a), transparent 0 55%, var(--orange) 72%, var(--blue) 90%, transparent 100%);
  -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);-webkit-mask-composite:xor;
  mask:linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0);
  animation:spin 7s linear infinite;
}
@keyframes spin{to{--a:360deg;}}
.hero .hlogo{height:92px;width:auto;flex:none;filter:drop-shadow(0 14px 18px rgba(14,58,102,.30));animation:floaty 5s ease-in-out infinite;}
@keyframes floaty{0%,100%{transform:translateY(0) rotate(-2deg);}50%{transform:translateY(-8px) rotate(2deg);}}
.hero .ht{
  font-size:2.1rem;font-weight:800;letter-spacing:-.035em;line-height:1.08;
  background:linear-gradient(90deg,#0F5CB0 0%,#1565C0 35%,#FF8A00 85%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.hero .hp{margin:.45rem 0 0;color:var(--mut);max-width:620px;font-size:1.02rem;}
.hero .hb{margin-bottom:8px;}

/* ---------- Bandeau défilant ---------- */
.ticker{overflow:hidden;border-radius:16px;margin:0 0 20px;padding:11px 0;color:#fff;
  background:linear-gradient(90deg,#0E3A66,#1565C0 60%,#0E3A66);box-shadow:0 14px 34px -16px rgba(14,58,102,.8);}
.ticker .track{display:inline-flex;white-space:nowrap;animation:marquee 38s linear infinite;}
.ticker:hover .track{animation-play-state:paused;}
.ticker .ti{padding:0 28px;font-weight:500;font-size:.92rem;}
.ticker .ti::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:10px;background:var(--c);box-shadow:0 0 12px var(--c);}
@keyframes marquee{to{transform:translateX(-50%);}}

/* ---------- KPI ---------- */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:16px;margin:4px 0 24px;}
.kpi{
  position:relative;padding:18px 20px 20px;border-radius:24px;overflow:hidden;
  transition:transform .28s cubic-bezier(.2,.8,.2,1), box-shadow .28s;animation:rise .6s both;
}
.kpi:hover{transform:translateY(-6px) rotate(-.4deg);box-shadow:0 1px 0 rgba(255,255,255,.95) inset, 0 26px 50px -18px var(--c);}
.kpi::after{content:"";position:absolute;left:0;bottom:0;width:100%;height:5px;background:linear-gradient(90deg,var(--c),transparent);}
.kpi .top{display:flex;align-items:center;gap:12px;}
.kpi .ico{
  width:42px;height:42px;border-radius:14px;display:grid;place-items:center;font-size:1.25rem;flex:none;
  background:linear-gradient(135deg,var(--c),color-mix(in srgb, var(--c) 55%, #fff));box-shadow:0 10px 20px -8px var(--c);
}
.kpi .lab{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);font-weight:600;}
.kpi .val{font-family:'JetBrains Mono',monospace;font-size:1.65rem;font-weight:700;margin-top:12px;color:var(--ink);}
.kpi .sub{font-size:.82rem;color:var(--mut);margin-top:3px;}

/* ---------- Sections, lignes, pastilles ---------- */
.sec{display:flex;align-items:center;gap:10px;margin:22px 0 10px;font-weight:700;font-size:1.08rem;color:var(--ink);}
.sec::before{content:"";width:10px;height:10px;border-radius:3px;transform:rotate(45deg);background:linear-gradient(135deg,var(--blue),var(--orange));}
.row-card{
  display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 18px;margin-bottom:9px;
  border-radius:18px;border-left:5px solid var(--c);transition:transform .22s, box-shadow .22s;animation:rise .5s both;
}
.row-card:hover{transform:translateX(5px);box-shadow:0 1px 0 rgba(255,255,255,.95) inset, 0 18px 36px -16px var(--c);}
.row-card .nm{font-weight:600;color:var(--ink);}
.row-card .meta{color:var(--mut);font-size:.82rem;margin-top:2px;}
.row-card .amt{font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--c);white-space:nowrap;text-align:right;}
.pill{
  display:inline-block;padding:3px 11px;border-radius:999px;font-size:.7rem;font-weight:700;letter-spacing:.05em;
  background:color-mix(in srgb, var(--c) 14%, transparent);color:var(--c);
  border:1px solid color-mix(in srgb, var(--c) 40%, transparent);
}
.dot-live{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:6px;animation:pulse 1.8s infinite;}
.ring-card{display:flex;align-items:center;gap:20px;padding:18px 22px;border-radius:24px;margin-bottom:12px;}
.ring{width:104px;height:104px;border-radius:50%;flex:none;display:grid;place-items:center;
  background:conic-gradient(var(--c) calc(var(--p) * 1%), rgba(14,58,102,.10) 0);box-shadow:0 12px 26px -12px var(--c);}
.ring .in{width:78px;height:78px;border-radius:50%;background:#fff;display:grid;place-items:center;
  font-family:'JetBrains Mono',monospace;font-weight:700;font-size:1.25rem;color:var(--ink);}
.ring-card .rt{font-weight:700;font-size:1.05rem;} .ring-card .rs{color:var(--mut);font-size:.88rem;margin-top:3px;}
.pay-card{
  max-width:520px;margin:10px auto;padding:36px 32px;border-radius:30px;text-align:center;
}
.pay-card .price{font-family:'JetBrains Mono',monospace;font-size:2.8rem;font-weight:700;
  background:linear-gradient(90deg,var(--blue),var(--orange));-webkit-background-clip:text;background-clip:text;color:transparent;}
.pay-card .per{color:var(--mut);margin-bottom:14px;}
.pay-card ul{list-style:none;padding:0;margin:16px 0 0;text-align:left;display:inline-block;}
.pay-card li{padding:5px 0;color:var(--ink);}
.pay-card li::before{content:"✦";color:var(--orange);margin-right:10px;}

/* ---------- Connexion ---------- */
.login-hero{text-align:center;margin:6px 0 18px;animation:rise .7s both;}
.login-hero img{width:min(300px,70%);filter:drop-shadow(0 22px 28px rgba(14,58,102,.30));animation:floaty 6s ease-in-out infinite;}
.login-hero .tag{color:var(--mut);margin-top:6px;font-size:1.02rem;}
.stMain:has(.login-marker) .block-container{max-width:600px;}
.stMain:has(.login-marker) [data-testid="stTabs"]{
  background:var(--glass);backdrop-filter:blur(18px) saturate(165%);border:1px solid var(--glass-line);
  box-shadow:var(--shadow);border-radius:26px;padding:10px 22px 22px;
}

/* ---------- Widgets Streamlit ---------- */
[data-testid="stBaseButton-primary"], button[kind="primary"], [data-testid="stBaseButton-primaryFormSubmit"],
div.stLinkButton > a, a[data-testid^="stBaseLinkButton"]{
  background:linear-gradient(135deg,#FFA62B,#FF7A00)!important;color:#fff!important;font-weight:700!important;
  border:0!important;border-radius:14px!important;box-shadow:0 14px 28px -12px rgba(255,122,0,.95);
  transition:transform .18s, filter .2s, box-shadow .2s;
}
[data-testid="stBaseButton-primary"] p, button[kind="primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p,
div.stLinkButton > a p{color:#fff!important;font-weight:700;}
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover,
div.stLinkButton > a:hover{transform:translateY(-3px);filter:brightness(1.06);box-shadow:0 20px 34px -10px rgba(255,122,0,.95);}
[data-testid="stBaseButton-secondary"], button[kind="secondary"], [data-testid="stBaseButton-secondaryFormSubmit"]{
  background:rgba(255,255,255,.55)!important;border:1.5px solid rgba(21,101,192,.5)!important;border-radius:14px!important;
  color:var(--blue)!important;font-weight:600;transition:all .2s;
}
[data-testid="stBaseButton-secondary"]:hover, button[kind="secondary"]:hover{
  background:rgba(21,101,192,.10)!important;box-shadow:0 10px 24px -10px rgba(21,101,192,.7);transform:translateY(-2px);
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]{background:rgba(255,255,255,.08)!important;border-color:rgba(255,255,255,.45)!important;color:#fff!important;}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p{color:#fff!important;}
div[data-baseweb="input"], div[data-baseweb="select"] > div, .stTextArea textarea{
  background:rgba(255,255,255,.66)!important;border:1px solid rgba(14,58,102,.16)!important;border-radius:14px!important;
}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within{
  border-color:var(--blue)!important;box-shadow:0 0 0 4px rgba(21,101,192,.16)!important;
}
div[data-baseweb="input"] > div, div[data-baseweb="base-input"], div[data-baseweb="input"] input{background:transparent!important;}
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stTextArea"] textarea{background:rgba(255,255,255,.72)!important;border-radius:14px!important;}
[data-testid="stSelectbox"] [data-baseweb="select"]{background:rgba(255,255,255,.72)!important;border-radius:14px!important;}
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div > div{background:transparent!important;}
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div{width:100%;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]{display:flex;}
button[data-baseweb="tab"]{font-weight:600;color:var(--mut);}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--blue);}
div[data-baseweb="tab-highlight"]{background:linear-gradient(90deg,var(--blue),var(--orange))!important;height:3px!important;}
[data-testid="stAlert"]{border-radius:16px;border:1px solid var(--glass-line);backdrop-filter:blur(10px);}
[data-testid="stExpander"]{border:1px solid var(--glass-line)!important;border-radius:16px!important;background:rgba(255,255,255,.5);}
[data-testid="stDataFrame"]{border:1px solid var(--glass-line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow);}
::-webkit-scrollbar{width:10px;height:10px;}
::-webkit-scrollbar-thumb{background:rgba(14,58,102,.28);border-radius:10px;}

@keyframes rise{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(31,157,107,.6);}70%{box-shadow:0 0 0 10px rgba(31,157,107,0);}100%{box-shadow:0 0 0 0 rgba(31,157,107,0);}}
@media (prefers-reduced-motion:reduce){
  .stApp, .hero::before, .hero .hlogo, .ticker .track, .login-hero img{animation:none!important;}
}
@media (max-width:640px){
  .hero{padding:18px;gap:14px;flex-direction:column;align-items:flex-start;} .hero .ht{font-size:1.5rem;} .hero .hlogo{height:64px;}
  .kpi .val{font-size:1.35rem;} .row-card{flex-direction:column;align-items:flex-start;gap:6px;} .row-card .amt{text-align:left;}
  .ring-card{flex-direction:column;text-align:center;}
}
</style>
"""


def inject_theme():
    st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------
def esc(valeur) -> str:
    """Échappe du texte saisi par l'utilisateur avant de l'insérer dans du HTML."""
    return html.escape("" if valeur is None else str(valeur))


def fcfa(montant) -> str:
    return f"{float(montant):,.0f}".replace(",", " ") + " F"


@lru_cache(maxsize=None)
def _data_uri(nom_fichier: str) -> str:
    donnees = (ASSETS / nom_fichier).read_bytes()
    return "data:image/png;base64," + base64.b64encode(donnees).decode()


def logo_path(kind: str = "full") -> str:
    return str(ASSETS / ("logo.png" if kind == "full" else "logo_icon.png"))


def pdf_logo(largeur_cm: float = 3.2):
    """Logo prêt à être placé en tête d'un PDF reportlab."""
    from reportlab.lib.units import cm
    from reportlab.platypus import Image
    from PIL import Image as PILImage
    w, h = PILImage.open(logo_path("full")).size
    return Image(logo_path("full"), width=largeur_cm * cm, height=largeur_cm * cm * h / w, hAlign="LEFT", mask="auto")


# ----------------------------------------------------------------------
# Composants
# ----------------------------------------------------------------------
def brand_header(sous_titre: str = "Gère ton stock. Suis tes crédits. Fais grandir ta boutique."):
    st.markdown(
        f'<span class="login-marker"></span><div class="login-hero"><img src="{_data_uri("logo.png")}" alt="BizStock">'
        f'<div class="tag">{esc(sous_titre)}</div></div>',
        unsafe_allow_html=True,
    )


def sidebar_brand(nom_boutique: str):
    st.markdown(
        f'<div class="brand-card"><img src="{_data_uri("logo.png")}" alt="BizStock">'
        f'<div class="shop">{esc(nom_boutique)}</div></div>',
        unsafe_allow_html=True,
    )


def hero(titre: str, sous_titre: str = "", badge: str = ""):
    badge_html = (f'<div class="hb"><span class="pill" style="--c:{TONES["mint"]}"><span class="dot-live"></span>{esc(badge)}</span></div>'
                  if badge else "")
    st.markdown(
        f'<div class="hero"><img class="hlogo" src="{_data_uri("logo_icon.png")}" alt="">'
        f'<div>{badge_html}<div class="ht">{esc(titre)}</div><p class="hp">{esc(sous_titre)}</p></div></div>',
        unsafe_allow_html=True,
    )


def section(titre: str):
    st.markdown(f'<div class="sec">{esc(titre)}</div>', unsafe_allow_html=True)


def kpi_grid(items: list[dict]):
    cartes = ""
    for i, it in enumerate(items):
        couleur = TONES.get(it.get("tone", "mint"), TONES["mint"])
        sub = f'<div class="sub">{esc(it["sub"])}</div>' if it.get("sub") else ""
        icone = esc(it.get("icon", "◆"))
        cartes += (
            f'<div class="kpi" style="--c:{couleur};animation-delay:{i * 80}ms">'
            f'<div class="top"><div class="ico">{icone}</div><div class="lab">{esc(it["label"])}</div></div>'
            f'<div class="val">{esc(it["value"])}</div>{sub}</div>'
        )
    st.markdown(f'<div class="kpi-grid">{cartes}</div>', unsafe_allow_html=True)


def row_card_html(titre: str, meta: str, montant: str, tone: str = "mint", pastille: str = "") -> str:
    couleur = TONES.get(tone, TONES["mint"])
    p = f'<span class="pill" style="--c:{couleur}">{esc(pastille)}</span>' if pastille else ""
    return (
        f'<div class="row-card" style="--c:{couleur}"><div><div class="nm">{esc(titre)} {p}</div>'
        f'<div class="meta">{esc(meta)}</div></div><div class="amt">{esc(montant)}</div></div>'
    )


def render_rows(lignes_html: list[str]):
    if lignes_html:
        st.markdown("".join(lignes_html), unsafe_allow_html=True)


def ticker(elements: list[tuple[str, str]]):
    """Bandeau défilant. elements = [(tone, texte), ...]"""
    if not elements:
        return
    morceau = "".join(f'<span class="ti" style="--c:{TONES.get(t, TONES["amber"])}">{esc(txt)}</span>' for t, txt in elements)
    st.markdown(f'<div class="ticker"><div class="track">{morceau}{morceau}</div></div>', unsafe_allow_html=True)


def health_ring(pourcentage: float, titre: str, sous_titre: str = ""):
    pct = max(0, min(100, round(pourcentage)))
    tone = "mint" if pct >= 80 else ("amber" if pct >= 50 else "coral")
    st.markdown(
        f'<div class="ring-card"><div class="ring" style="--c:{TONES[tone]};--p:{pct}"><div class="in">{pct}%</div></div>'
        f'<div><div class="rt">{esc(titre)}</div><div class="rs">{esc(sous_titre)}</div></div></div>',
        unsafe_allow_html=True,
    )


def flash(message: str, kind: str = "success"):
    """Mémorise un message à afficher après le prochain rechargement (st.rerun l'effacerait sinon)."""
    st.session_state["flash"] = (kind, message)


def show_flash():
    data = st.session_state.pop("flash", None)
    if not data:
        return
    kind, message = data
    {"success": st.success, "error": st.error, "warning": st.warning, "info": st.info}.get(kind, st.info)(message)
