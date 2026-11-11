"""
Thème visuel « Solaire néon » : fond noir-vert profond, vert menthe et lime électrique,
ambre et corail pour les alertes. Aucun violet. Injecté une fois au démarrage de l'app.
"""
import html

import streamlit as st

TONES = {
    "mint": "#00F5A0",
    "lime": "#C8FF00",
    "amber": "#FFB020",
    "coral": "#FF5A36",
    "teal": "#0FD3C0",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

:root{
  --bg:#050908; --panel:rgba(255,255,255,.045); --line:rgba(255,255,255,.09);
  --txt:#E6F4EC; --mut:#86A196;
  --mint:#00F5A0; --lime:#C8FF00; --amber:#FFB020; --coral:#FF5A36; --teal:#0FD3C0;
}
html, body, .stApp, [data-testid="stSidebar"] *{font-family:'Space Grotesk',system-ui,sans-serif;}
.stApp{
  color:var(--txt);
  background:
    linear-gradient(rgba(255,255,255,.022) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.022) 1px, transparent 1px),
    radial-gradient(900px 520px at 6% -6%, rgba(0,245,160,.17), transparent 62%),
    radial-gradient(820px 520px at 104% 106%, rgba(255,176,32,.14), transparent 62%),
    radial-gradient(520px 360px at 92% 2%, rgba(200,255,0,.07), transparent 62%),
    var(--bg);
  background-size:46px 46px,46px 46px,auto,auto,auto,auto;
  background-attachment:fixed;
}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2.2rem;max-width:1180px;}
h1,h2,h3{letter-spacing:-.02em;font-weight:700;}
h1{background:linear-gradient(90deg,var(--mint),var(--lime));-webkit-background-clip:text;background-clip:text;color:transparent;}
hr{border-color:var(--line)!important;}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg, rgba(7,19,15,.97), rgba(5,9,8,.99));
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] div[role="radiogroup"]{gap:6px;}
[data-testid="stSidebar"] label[data-baseweb="radio"]{
  padding:10px 14px;border-radius:12px;border:1px solid transparent;width:100%;transition:all .2s;
}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{background:rgba(255,255,255,.05);}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){
  background:linear-gradient(90deg, rgba(0,245,160,.18), rgba(200,255,0,.05));
  border-color:rgba(0,245,160,.45);box-shadow:inset 3px 0 0 var(--mint);
}
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child{display:none;}
.brand{display:flex;align-items:center;gap:12px;padding:6px 4px 14px;}
.brand .logo{
  width:42px;height:42px;border-radius:13px;display:grid;place-items:center;font-size:1.25rem;
  background:linear-gradient(135deg,var(--mint),var(--lime));color:#03110B;
  box-shadow:0 0 28px rgba(0,245,160,.55);
}
.brand .t{font-weight:700;line-height:1.1;}
.brand .s{font-size:.75rem;color:var(--mut);}

/* ---------- Hero ---------- */
.hero{
  position:relative;padding:26px 30px;border-radius:24px;margin-bottom:22px;overflow:hidden;
  border:1px solid var(--line);
  background:linear-gradient(120deg, rgba(0,245,160,.11), rgba(255,176,32,.07) 62%, rgba(255,255,255,.02));
  animation:rise .6s both;
}
.hero::after{
  content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;
  background:radial-gradient(circle, rgba(200,255,0,.30), transparent 68%);
}
.hero .ht{
  font-size:2.05rem;font-weight:700;letter-spacing:-.03em;line-height:1.1;
  background:linear-gradient(90deg,var(--mint),var(--lime) 45%,var(--amber),var(--mint));
  background-size:220% auto;-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:shine 7s linear infinite;
}
.hero .hp{margin:.5rem 0 0;color:var(--mut);max-width:640px;}
.hero .hb{margin-bottom:10px;}

/* ---------- KPI ---------- */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:4px 0 24px;}
.kpi{
  position:relative;padding:18px 20px;border-radius:20px;background:var(--panel);
  border:1px solid var(--line);backdrop-filter:blur(10px);overflow:hidden;
  transition:transform .25s, border-color .25s, box-shadow .25s;animation:rise .6s both;
}
.kpi:hover{transform:translateY(-3px);border-color:var(--c);box-shadow:0 14px 40px -14px var(--c);}
.kpi::after{
  content:"";position:absolute;right:-34px;top:-34px;width:120px;height:120px;border-radius:50%;
  background:radial-gradient(circle,var(--c),transparent 70%);opacity:.22;
}
.kpi .lab{font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut);}
.kpi .val{
  font-family:'JetBrains Mono',monospace;font-size:1.65rem;font-weight:700;margin-top:8px;color:var(--c);
  text-shadow:0 0 26px color-mix(in srgb, var(--c) 45%, transparent);
}
.kpi .sub{font-size:.8rem;color:var(--mut);margin-top:4px;}

/* ---------- Lignes / pastilles ---------- */
.sec{display:flex;align-items:center;gap:10px;margin:22px 0 10px;font-weight:700;font-size:1.05rem;}
.sec::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--mint);box-shadow:0 0 14px var(--mint);}
.row-card{
  display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 16px;margin-bottom:8px;
  border-radius:14px;background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--c);
  transition:transform .2s, background .2s;animation:rise .5s both;
}
.row-card:hover{transform:translateX(3px);background:rgba(255,255,255,.07);}
.row-card .nm{font-weight:600;}
.row-card .meta{color:var(--mut);font-size:.8rem;margin-top:2px;}
.row-card .amt{font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--c);white-space:nowrap;text-align:right;}
.pill{
  display:inline-block;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:600;letter-spacing:.05em;
  background:color-mix(in srgb, var(--c) 16%, transparent);color:var(--c);
  border:1px solid color-mix(in srgb, var(--c) 42%, transparent);
}
.dot-live{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--mint);margin-right:6px;
  box-shadow:0 0 0 0 rgba(0,245,160,.7);animation:pulse 1.8s infinite;}
.pay-card{
  max-width:520px;margin:10px auto;padding:34px 32px;border-radius:26px;text-align:center;
  background:linear-gradient(160deg, rgba(0,245,160,.10), rgba(255,255,255,.03) 55%, rgba(255,176,32,.08));
  border:1px solid rgba(0,245,160,.35);box-shadow:0 30px 80px -30px rgba(0,245,160,.45);
}
.pay-card .price{font-family:'JetBrains Mono',monospace;font-size:2.7rem;font-weight:700;color:var(--lime);
  text-shadow:0 0 32px rgba(200,255,0,.45);}
.pay-card .per{color:var(--mut);margin-bottom:14px;}
.pay-card ul{list-style:none;padding:0;margin:16px 0 0;text-align:left;display:inline-block;}
.pay-card li{padding:4px 0;color:var(--txt);}
.pay-card li::before{content:"✦";color:var(--mint);margin-right:10px;}

/* ---------- Widgets Streamlit ---------- */
[data-testid="stBaseButton-primary"], button[kind="primary"], [data-testid="stBaseButton-primaryFormSubmit"],
div.stLinkButton > a, a[data-testid^="stBaseLinkButton"]{
  background:linear-gradient(135deg,var(--mint),var(--lime))!important;color:#03110B!important;font-weight:700!important;
  border:0!important;border-radius:12px!important;box-shadow:0 10px 28px -12px rgba(0,245,160,.8);
  transition:transform .15s, filter .2s, box-shadow .2s;
}
[data-testid="stBaseButton-primary"] p, button[kind="primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p,
div.stLinkButton > a p{color:#03110B!important;font-weight:700;}
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover,
div.stLinkButton > a:hover{transform:translateY(-2px);filter:brightness(1.08);box-shadow:0 16px 36px -10px rgba(200,255,0,.7);}
[data-testid="stBaseButton-secondary"], button[kind="secondary"], [data-testid="stBaseButton-secondaryFormSubmit"]{
  background:transparent!important;border:1px solid rgba(0,245,160,.45)!important;border-radius:12px!important;color:var(--mint)!important;
  transition:all .2s;
}
[data-testid="stBaseButton-secondary"]:hover, button[kind="secondary"]:hover{
  background:rgba(0,245,160,.10)!important;box-shadow:0 0 24px -6px rgba(0,245,160,.6);
}
div[data-baseweb="input"], div[data-baseweb="select"] > div, .stTextArea textarea{
  background:rgba(255,255,255,.04)!important;border:1px solid var(--line)!important;border-radius:12px!important;
}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within{
  border-color:var(--mint)!important;box-shadow:0 0 0 3px rgba(0,245,160,.18)!important;
}
div[data-baseweb="input"] input{background:transparent!important;}
button[data-baseweb="tab"]{font-weight:600;color:var(--mut);}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--mint);}
div[data-baseweb="tab-highlight"]{background:linear-gradient(90deg,var(--mint),var(--lime))!important;height:3px!important;}
[data-testid="stAlert"]{border-radius:14px;border:1px solid var(--line);}
[data-testid="stExpander"]{border:1px solid var(--line)!important;border-radius:14px!important;background:var(--panel);}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:14px;overflow:hidden;}
::-webkit-scrollbar{width:10px;height:10px;}
::-webkit-scrollbar-thumb{background:rgba(0,245,160,.25);border-radius:10px;}

@keyframes shine{to{background-position:220% center;}}
@keyframes rise{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(0,245,160,.65);}70%{box-shadow:0 0 0 10px rgba(0,245,160,0);}100%{box-shadow:0 0 0 0 rgba(0,245,160,0);}}
@media (max-width:640px){
  .hero{padding:20px;} .hero .ht{font-size:1.5rem;} .kpi .val{font-size:1.35rem;}
  .row-card{flex-direction:column;align-items:flex-start;gap:6px;} .row-card .amt{text-align:left;}
}
</style>
"""


def inject_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(valeur) -> str:
    """Échappe du texte saisi par l'utilisateur avant de l'insérer dans du HTML."""
    return html.escape("" if valeur is None else str(valeur))


def fcfa(montant) -> str:
    return f"{float(montant):,.0f}".replace(",", " ") + " F"


def hero(titre: str, sous_titre: str = "", badge: str = ""):
    badge_html = f'<div class="hb"><span class="pill" style="--c:{TONES["mint"]}"><span class="dot-live"></span>{esc(badge)}</span></div>' if badge else ""
    st.markdown(
        f'<div class="hero">{badge_html}<div class="ht">{esc(titre)}</div><p class="hp">{esc(sous_titre)}</p></div>',
        unsafe_allow_html=True,
    )


def section(titre: str):
    st.markdown(f'<div class="sec">{esc(titre)}</div>', unsafe_allow_html=True)


def kpi_grid(items: list[dict]):
    cartes = ""
    for i, it in enumerate(items):
        couleur = TONES.get(it.get("tone", "mint"), TONES["mint"])
        sub = f'<div class="sub">{esc(it["sub"])}</div>' if it.get("sub") else ""
        cartes += (
            f'<div class="kpi" style="--c:{couleur};animation-delay:{i * 70}ms">'
            f'<div class="lab">{esc(it["label"])}</div><div class="val">{esc(it["value"])}</div>{sub}</div>'
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


def flash(message: str, kind: str = "success"):
    """Mémorise un message à afficher après le prochain rechargement (st.rerun l'effacerait sinon)."""
    st.session_state["flash"] = (kind, message)


def show_flash():
    data = st.session_state.pop("flash", None)
    if not data:
        return
    kind, message = data
    {"success": st.success, "error": st.error, "warning": st.warning, "info": st.info}.get(kind, st.info)(message)
