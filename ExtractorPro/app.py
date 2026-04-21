# ── Verificação e instalação automática de dependências ──────────────────────
import sys
import subprocess

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

_DEPENDENCIAS = [
    ("customtkinter", "customtkinter"),
    ("playwright",    "playwright"),
]

def _instalar(pacote):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pacote],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )

for _modulo, _pacote in _DEPENDENCIAS:
    try:
        __import__(_modulo)
    except ImportError:
        _instalar(_pacote)

# Verifica se o Chromium do Playwright está instalado
import pathlib
_ms_pw = pathlib.Path.home() / "AppData" / "Local" / "ms-playwright"
_chromium_ok = any(_ms_pw.glob("chromium-*/chrome-win/chrome.exe")) if _ms_pw.exists() else False
if not _chromium_ok:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )
del _ms_pw, _chromium_ok
# ─────────────────────────────────────────────────────────────────────────────

import customtkinter as ctk
import threading
import csv
import re
import time
import os
import json
import tempfile
import webbrowser

from datetime import datetime
from tkinter import filedialog
import tkinter as tk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Portable: pasta do .exe (ou do .py em dev) ────────────────────────────────
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR       = get_base_dir()
HISTORICO_FILE = os.path.join(BASE_DIR, "historico.json")

# ── Portable: Chromium embutido ou ms-playwright ──────────────────────────────
def get_chromium_path():
    # 1. Pasta chromium/ ao lado do .exe (portable)
    candidates = [
        os.path.join(BASE_DIR, "chromium", "chrome-win", "chrome.exe"),
        os.path.join(BASE_DIR, "chromium", "chrome.exe"),
        os.path.join(BASE_DIR, "chromium", "chromium.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    # 2. ms-playwright no AppData do usuario (instalacao padrao Playwright)
    import pathlib
    ms_pw = pathlib.Path.home() / "AppData" / "Local" / "ms-playwright"
    if ms_pw.exists():
        for d in sorted(ms_pw.glob("chromium-*"), reverse=True):
            exe = d / "chrome-win" / "chrome.exe"
            if exe.exists():
                return str(exe)

    return None

CHROMIUM_PATH = get_chromium_path()

from cidades import CIDADES_POR_ESTADO

SEGMENTO_PADRAO = "Preencher segmento"
TERMOS_PADRAO   = ["Preencher termo"]
COLUNAS         = [("NOME", 380), ("TELEFONE / WHATSAPP", 220), ("ENDEREÇO", 480)]


# ── Dialog ────────────────────────────────────────────────────────────────────
class Dialog(ctk.CTkToplevel):
    _CFG = {
        "info":    ("⬡", "#00e5ff"),
        "success": ("✓", "#00e5ff"),
        "warning": ("⚠", "#ff9f43"),
        "error":   ("✕", "#ff4d6d"),
        "confirm": ("?", "#a29bfe"),
    }

    def __init__(self, master, tipo="info", titulo="", mensagem="", on_yes=None):
        super().__init__(master)
        self._on_yes = on_yes
        icone, cor   = self._CFG.get(tipo, self._CFG["info"])
        self.overrideredirect(True)
        self.configure(fg_color="#0f1117")
        self.resizable(False, False)

        borda = ctk.CTkFrame(self, fg_color=cor, corner_radius=14)
        borda.pack()
        corpo = ctk.CTkFrame(borda, fg_color="#161b27", corner_radius=13)
        corpo.pack(padx=2, pady=2)

        ic_frame = ctk.CTkFrame(corpo, fg_color="#0f1117", corner_radius=40, width=60, height=60)
        ic_frame.pack(pady=(28, 0))
        ic_frame.pack_propagate(False)
        ctk.CTkLabel(ic_frame, text=icone,
                     font=ctk.CTkFont(family="Courier New", size=26, weight="bold"),
                     text_color=cor).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(corpo, text=titulo, font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#c9d1e0", wraplength=300).pack(pady=(12, 0), padx=36)
        if mensagem:
            ctk.CTkLabel(corpo, text=mensagem, font=ctk.CTkFont(size=12),
                         text_color="#8892a4", justify="center", wraplength=300).pack(pady=(6, 0), padx=36)

        ctk.CTkFrame(corpo, height=1, fg_color="#2a3042").pack(fill="x", padx=24, pady=20)
        btn_row = ctk.CTkFrame(corpo, fg_color="transparent")
        btn_row.pack(pady=(0, 24), padx=24)

        def _esc(h):
            h = h.lstrip("#")
            r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
            return f"#{max(0,r-30):02x}{max(0,g-30):02x}{max(0,b-30):02x}"

        if tipo == "confirm":
            ctk.CTkButton(btn_row, text="Cancelar", width=118, height=36,
                          fg_color="#1e2535", hover_color="#2a3042",
                          text_color="#8892a4", font=ctk.CTkFont(size=12),
                          corner_radius=8, command=self._fechar).pack(side="left", padx=(0,8))
            ctk.CTkButton(btn_row, text="Confirmar", width=118, height=36,
                          fg_color=cor, hover_color=_esc(cor),
                          text_color="#0f1117", font=ctk.CTkFont(size=12, weight="bold"),
                          corner_radius=8, command=self._confirmar).pack(side="left")
        else:
            ctk.CTkButton(btn_row, text="OK", width=140, height=36,
                          fg_color=cor, hover_color=_esc(cor),
                          text_color="#0f1117", font=ctk.CTkFont(size=13, weight="bold"),
                          corner_radius=8, command=self._fechar).pack()

        self.bind("<Return>", lambda e: self._confirmar() if tipo=="confirm" else self._fechar())
        self.bind("<Escape>", lambda e: self._fechar())
        self.update_idletasks()
        w = self.winfo_reqwidth(); h = self.winfo_reqheight()
        try:
            mx = master.winfo_rootx() + master.winfo_width()  // 2
            my = master.winfo_rooty() + master.winfo_height() // 2
        except Exception:
            mx = self.winfo_screenwidth()  // 2
            my = self.winfo_screenheight() // 2
        self.geometry(f"{w}x{h}+{mx-w//2}+{my-h//2}")
        self.lift(); self.focus_force(); self.grab_set()

    def _fechar(self):
        self.grab_release(); self.destroy()
    def _confirmar(self):
        self.grab_release(); self.destroy()
        if self._on_yes: self._on_yes()


# ── Histórico ─────────────────────────────────────────────────────────────────
def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def salvar_historico(historico):
    try:
        with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def tocar_som():
    try:
        if os.name == 'nt':
            import winsound; winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        else:
            print('\a', end='', flush=True)
    except Exception:
        pass

def extrair_telefone(texto):
    m = re.search(r'(?:\+55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4}[\s-]?\d{4}', texto)
    return m.group(0).strip() if m else ""

def slug(texto):
    return re.sub(r'[^a-zA-Z0-9À-ú]', '_', texto).strip('_')


# ── Scraper ───────────────────────────────────────────────────────────────────
def scrape(estado, cidades, termos, callbacks, stop_event):
    on_log          = callbacks["on_log"]
    on_result       = callbacks["on_result"]
    on_done         = callbacks["on_done"]
    on_cidade_start = callbacks.get("on_cidade_start", lambda *a: None)
    on_cidade_found = callbacks.get("on_cidade_found", lambda *a: None)
    on_cidade_done  = callbacks.get("on_cidade_done",  lambda *a: None)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        on_log("❌ Playwright não instalado!")
        on_done(False)
        return

    todas = {}

    try:
        with sync_playwright() as p:
            launch_kwargs = dict(
                headless=True,
                args=["--lang=pt-BR", "--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"]
            )
            if CHROMIUM_PATH:
                launch_kwargs["executable_path"] = CHROMIUM_PATH

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                locale="pt-BR",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            total_cidades = len(cidades)

            for idx, cidade in enumerate(cidades):
                if stop_event.is_set():
                    break

                on_cidade_start(cidade, total_cidades, idx)
                on_log(f"📍 Buscando em {cidade}...")

                for termo in termos:
                    if stop_event.is_set():
                        break

                    query = f"{termo} {cidade} {estado}"
                    url   = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(2)

                        try:
                            btn = page.locator('button:has-text("Aceitar tudo")').first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                time.sleep(1)
                        except Exception:
                            pass

                        for _ in range(10):
                            if stop_event.is_set():
                                break
                            try:
                                page.evaluate("""
                                    const feed = document.querySelector('div[role="feed"]');
                                    if (feed) feed.scrollTop = feed.scrollHeight;
                                """)
                            except Exception:
                                pass
                            time.sleep(1.2)

                        try:
                            itens = page.locator('a[href*="/maps/place/"]').all()
                            links = list(set([
                                i.get_attribute("href") for i in itens
                                if i.get_attribute("href")
                            ]))
                        except Exception:
                            links = []

                        on_log(f"   🔎 '{termo}' → {len(links)} resultado(s)")

                        for link in links:
                            if stop_event.is_set():
                                break
                            if link in todas:
                                continue

                            try:
                                page.goto(link, wait_until="domcontentloaded", timeout=20000)
                                time.sleep(1.5)

                                nome = ""
                                try:
                                    nome = page.locator('h1').first.inner_text(timeout=3000)
                                except Exception:
                                    pass

                                if not nome:
                                    continue

                                telefone = ""
                                for sel in [
                                    '[data-tooltip="Copiar número de telefone"]',
                                    '[aria-label*="Telefone:"]',
                                    'button[aria-label*="telefone" i]',
                                ]:
                                    try:
                                        el = page.locator(sel).first
                                        if el.count():
                                            raw = el.get_attribute("aria-label") or el.inner_text()
                                            telefone = extrair_telefone(raw) or raw.replace("Telefone:", "").strip()
                                            break
                                    except Exception:
                                        pass

                                endereco = ""
                                for sel in [
                                    '[data-tooltip="Copiar endereço"]',
                                    '[aria-label*="Endereço:"]',
                                ]:
                                    try:
                                        el = page.locator(sel).first
                                        if el.count():
                                            endereco = (
                                                el.get_attribute("aria-label") or el.inner_text()
                                            ).replace("Endereço:", "").strip()
                                            break
                                    except Exception:
                                        pass

                                site = ""
                                try:
                                    el = page.locator('a[data-tooltip="Abrir site"]').first
                                    if el.count():
                                        site = el.get_attribute("href") or ""
                                except Exception:
                                    pass

                                reg = {
                                    "Nome":     nome,
                                    "Telefone": telefone,
                                    "Endereço": endereco,
                                    "Site":     site,
                                    "URL Maps": link,
                                }
                                todas[link] = reg
                                on_result(reg)
                                on_cidade_found(cidade, len(todas))

                            except Exception as e:
                                on_log(f"   ⚠️ Erro em empresa: {str(e)[:50]}")

                            time.sleep(0.8)

                    except Exception as e:
                        on_log(f"   ⚠️ Erro em '{cidade}' / '{termo}': {str(e)[:60]}")

                    time.sleep(1.5)

                on_cidade_done(cidade)

            try:
                browser.close()
            except Exception:
                pass

    except Exception as e:
        on_log(f"❌ Erro crítico no scraper: {str(e)}")
        on_done(False, str(e))
        return

    on_log(f"✅ Concluído! {len(todas)} empresa(s) encontrada(s).")
    on_done(True, list(todas.values()))


# ── PDF ───────────────────────────────────────────────────────────────────────
def gerar_pdf(resultados, estado, segmento, path):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        return False, "reportlab não instalado."

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2*cm, bottomMargin=2*cm)

    C_AZUL  = colors.HexColor("#00e5ff"); C_ESC  = colors.HexColor("#0f1117")
    C_HDR   = colors.HexColor("#1e2535"); C_PAR  = colors.HexColor("#13181f")
    C_TXT   = colors.HexColor("#c9d1e0"); C_CZ   = colors.HexColor("#8892a4")
    C_GRID  = colors.HexColor("#2a3042")

    sT  = ParagraphStyle("t",  fontSize=20, textColor=C_AZUL, fontName="Courier-Bold",   alignment=TA_LEFT, spaceAfter=6)
    sST = ParagraphStyle("st", fontSize=12, textColor=C_TXT,  fontName="Helvetica-Bold", alignment=TA_LEFT, spaceAfter=4)
    sI  = ParagraphStyle("i",  fontSize=9,  textColor=C_CZ,   fontName="Helvetica",      spaceAfter=2)
    sC  = ParagraphStyle("c",  fontSize=8,  textColor=C_TXT,  fontName="Helvetica",      leading=12, wordWrap='LTR')
    sTl = ParagraphStyle("tl", fontSize=8,  textColor=C_AZUL, fontName="Helvetica-Bold", leading=12)
    sH  = ParagraphStyle("h",  fontSize=8,  textColor=C_AZUL, fontName="Helvetica-Bold", leading=12)
    sR  = ParagraphStyle("r",  fontSize=7,  textColor=C_CZ,   fontName="Helvetica",      alignment=TA_CENTER)

    total = len(resultados); com_tel = sum(1 for r in resultados if r.get("Telefone"))
    ds    = datetime.now().strftime("%d/%m/%Y às %H:%M")
    larg  = A4[0] - 3*cm

    els = [
        Paragraph("ExtractorPro", sT),
        Paragraph(f"{segmento} — {estado}", sST),
        HRFlowable(width="100%", thickness=1, color=C_AZUL, spaceAfter=8, spaceBefore=4),
        Paragraph(f"Total: <b>{total}</b> empresas   •   Com telefone: <b>{com_tel}</b>   •   Gerado em: {ds}", sI),
        Spacer(1, 0.4*cm),
    ]

    dados = [[Paragraph("NOME",sH), Paragraph("TELEFONE",sH), Paragraph("ENDEREÇO",sH)]]
    for r in resultados:
        tem = bool(r.get("Telefone"))
        dados.append([Paragraph(r.get("Nome",""),sC),
                      Paragraph(r.get("Telefone") or "—", sTl if tem else sC),
                      Paragraph(r.get("Endereço",""),sC)])

    tab = Table(dados, colWidths=[larg*0.35,larg*0.20,larg*0.45], repeatRows=1)
    tab.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),C_HDR),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_ESC,C_PAR]),
        ("LINEBELOW",(0,0),(-1,0),1,C_AZUL),
        ("GRID",(0,1),(-1,-1),0.3,C_GRID),
        ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8), ("RIGHTPADDING",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))

    els += [tab, Spacer(1,0.6*cm),
            HRFlowable(width="100%",thickness=0.5,color=C_CZ,spaceAfter=6),
            Paragraph(f"Relatório gerado pelo ExtractorPro  •  {ds}", sR)]

    def fundo(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_ESC)
        canvas.rect(0,0,A4[0],A4[1],fill=True,stroke=False)
        canvas.restoreState()

    doc.build(els, onFirstPage=fundo, onLaterPages=fundo)
    return True, ""


# ── PDF Viewer ────────────────────────────────────────────────────────────────
class PDFViewer(ctk.CTkToplevel):
    def __init__(self, master, path):
        super().__init__(master)
        self.title(f"📄 {os.path.basename(path)}")
        self.geometry("950x750"); self.configure(fg_color="#0f1117")
        self.resizable(True,True); self.lift(); self.focus_force()
        try:
            import fitz; from PIL import Image, ImageTk
        except ImportError:
            Dialog(master,"error","Dependência ausente","pip install pymupdf pillow"); self.destroy(); return
        self.fitz=fitz; self.Image=Image; self.ImageTk=ImageTk
        self.doc=fitz.open(path); self.pagina=0; self.zoom=1.5; self.tk_img=None
        self._build_ui(); self._renderizar()

    def _build_ui(self):
        bar = ctk.CTkFrame(self, fg_color="#161b27", height=52, corner_radius=0)
        bar.pack(fill="x"); bar.pack_propagate(False)
        for txt, cmd, cor in [("◀",self._anterior,"#00e5ff"),("▶",self._proxima,"#00e5ff")]:
            ctk.CTkButton(bar,text=txt,width=48,height=34,fg_color="#1e2535",hover_color="#2a3042",
                          text_color=cor,font=ctk.CTkFont(size=16),command=cmd).pack(side="left",padx=2,pady=9)
        self.lbl_pagina = ctk.CTkLabel(bar,text="",font=ctk.CTkFont(size=13),text_color="#8892a4")
        self.lbl_pagina.pack(side="left",padx=16)
        for txt, cmd in [("＋",self._zoom_in),("－",self._zoom_out)]:
            ctk.CTkButton(bar,text=txt,width=44,height=34,fg_color="#1e2535",hover_color="#2a3042",
                          text_color="#ff9f43",font=ctk.CTkFont(size=16,weight="bold"),command=cmd).pack(side="right",padx=2,pady=9)
        ctk.CTkLabel(bar,text="Zoom",font=ctk.CTkFont(size=11),text_color="#5c6478").pack(side="right",padx=4)
        frame = tk.Frame(self, bg="#0f1117"); frame.pack(fill="both",expand=True)
        self.canvas = tk.Canvas(frame,bg="#0f1117",highlightthickness=0,cursor="hand2")
        sb_y = tk.Scrollbar(frame,orient="vertical",command=self.canvas.yview)
        sb_x = tk.Scrollbar(frame,orient="horizontal",command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=sb_y.set,xscrollcommand=sb_x.set)
        sb_y.pack(side="right",fill="y"); sb_x.pack(side="bottom",fill="x")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<MouseWheel>",self._scroll_mouse)
        self.canvas.bind("<Button-4>",lambda e: self.canvas.yview_scroll(-1,"units"))
        self.canvas.bind("<Button-5>",lambda e: self.canvas.yview_scroll(1,"units"))
        self.bind("<Left>",lambda e: self._anterior()); self.bind("<Right>",lambda e: self._proxima())
        self.bind("<plus>",lambda e: self._zoom_in()); self.bind("<minus>",lambda e: self._zoom_out())

    def _renderizar(self):
        pag=self.doc[self.pagina]; mat=self.fitz.Matrix(self.zoom,self.zoom); pix=pag.get_pixmap(matrix=mat)
        img=self.Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
        self.tk_img=self.ImageTk.PhotoImage(img); w=pix.width
        self.canvas.delete("all"); self.canvas.create_image(w//2,14,anchor="n",image=self.tk_img)
        self.canvas.configure(scrollregion=(0,0,w,pix.height+28)); self.canvas.yview_moveto(0)
        self.lbl_pagina.configure(text=f"Página  {self.pagina+1}  /  {len(self.doc)}")

    def _anterior(self):
        if self.pagina>0: self.pagina-=1; self._renderizar()
    def _proxima(self):
        if self.pagina<len(self.doc)-1: self.pagina+=1; self._renderizar()
    def _zoom_in(self):
        if self.zoom<4.0: self.zoom=round(self.zoom+0.25,2); self._renderizar()
    def _zoom_out(self):
        if self.zoom>0.5: self.zoom=round(self.zoom-0.25,2); self._renderizar()
    def _scroll_mouse(self,event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)),"units")


# ── Splash ────────────────────────────────────────────────────────────────────
class SplashScreen(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True); self.configure(fg_color="#0f1117")
        w,h=420,220; sw=self.winfo_screenwidth(); sh=self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        ctk.CTkLabel(self,text="⬡",font=ctk.CTkFont(family="Courier New",size=48,weight="bold"),
                     text_color="#00e5ff").pack(pady=(30,0))
        ctk.CTkLabel(self,text="ExtractorPro",font=ctk.CTkFont(family="Courier New",size=28,weight="bold"),
                     text_color="#00e5ff").pack()
        ctk.CTkLabel(self,text="Extrator profissional de empresas",
                     font=ctk.CTkFont(size=12),text_color="#8892a4").pack(pady=(4,16))
        bar = ctk.CTkProgressBar(self,width=320,height=4,fg_color="#1e2535",
                                 progress_color="#00e5ff",mode="indeterminate")
        bar.pack(); bar.start()
        self.lift(); self.focus_force()


# ── App ───────────────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ExtractorPro")
        self.geometry("1280x800")
        self.minsize(1100, 680)
        self.configure(fg_color="#0f1117")
        self.withdraw()

        self.resultados  = []
        self.stop_event  = threading.Event()
        self.rodando     = False
        self.ultimo_pdf  = None
        self.historico   = carregar_historico()
        if self.historico:
            self.resultados = list(self.historico[-1].get("resultados", []))
        self._filtro_var = tk.StringVar()
        self._filtro_var.trace_add("write", self._aplicar_filtro)

        self.log_frame         = None
        self.progress          = None
        self.scroll_resultados = None
        self.scroll_historico  = None
        self.dash_frame        = None
        self._abas_frames      = {}
        self._abas_btns        = {}
        self._aba_ativa        = tk.StringVar(value="resultados")

        self._prog_inicio       = None
        self._prog_cidades      = {}
        self._prog_cidade_atual = tk.StringVar(value="—")
        self._prog_cidade_refs  = {}
        self._prog_velocidade   = []

        splash = SplashScreen(self)
        self.after(2000, lambda: (splash.destroy(), self.deiconify(), self._build_ui()))

    def _build_ui(self):
        try:
            self._build_header()
            self._build_body()
            self._build_footer()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ctk.CTkLabel(self, text=f"Erro ao iniciar:\n{e}",
                         text_color="#ff4d6d", font=ctk.CTkFont(size=13),
                         wraplength=600).pack(expand=True)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="#161b27", corner_radius=0, height=70)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⬡  ExtractorPro",
                     font=ctk.CTkFont(family="Courier New", size=24, weight="bold"),
                     text_color="#00e5ff").pack(side="left", padx=24, pady=16)
        self.lbl_header_seg = ctk.CTkLabel(hdr,
            text=f"Extrator de empresas — {SEGMENTO_PADRAO}",
            font=ctk.CTkFont(size=13), text_color="#8892a4")
        self.lbl_header_seg.pack(side="left", padx=4)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="#0a0d13", corner_radius=0, height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        total_buscas   = len(self.historico)
        total_empresas = sum(h.get("total", 0) for h in self.historico)
        self.lbl_footer = ctk.CTkLabel(footer,
            text=self._footer_texto(total_buscas, total_empresas),
            font=ctk.CTkFont(family="Courier New", size=11), text_color="#3a4252")
        self.lbl_footer.pack(side="left", padx=16)
        ctk.CTkLabel(footer, text="ExtractorPro v1.0",
                     font=ctk.CTkFont(size=10), text_color="#2a3042").pack(side="right", padx=16)

    def _footer_texto(self, buscas, empresas):
        return f"⬡  {buscas} busca{'s' if buscas != 1 else ''} realizadas  •  {empresas} empresa{'s' if empresas != 1 else ''} coletadas"

    def _atualizar_footer(self):
        if not hasattr(self, "lbl_footer"): return
        total_buscas   = len(self.historico)
        total_empresas = sum(h.get("total", 0) for h in self.historico)
        self.lbl_footer.configure(text=self._footer_texto(total_buscas, total_empresas))

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=0, minsize=270)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_sidebar(body)
        self._build_main(body)

    def _build_sidebar(self, parent):
        outer = ctk.CTkFrame(parent, fg_color="#161b27", corner_radius=12, width=270)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0,14))
        outer.grid_propagate(False)
        side = ctk.CTkScrollableFrame(outer, fg_color="transparent", width=240)
        side.pack(fill="both", expand=True)
        pad = {"padx": 18, "pady": (0,10)}

        ctk.CTkLabel(side, text="SEGMENTO / TIPO DE EMPRESA",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").pack(anchor="w", padx=18, pady=(20,4))
        self.entry_segmento = ctk.CTkEntry(side, width=220, height=36, fg_color="#0f1117",
            border_color="#00e5ff", border_width=1, font=ctk.CTkFont(size=13),
            text_color="#c9d1e0", placeholder_text="ex: clínica odontológica")
        self.entry_segmento.insert(0, SEGMENTO_PADRAO)
        self.entry_segmento.pack(**pad)
        self.entry_segmento.bind("<FocusOut>", self._on_segmento_change)
        self.entry_segmento.bind("<Return>",   self._on_segmento_change)

        ctk.CTkLabel(side, text="ESTADO", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").pack(anchor="w", padx=18, pady=(4,4))
        self.combo_estado = ctk.CTkComboBox(side, values=sorted(CIDADES_POR_ESTADO.keys()),
            width=220, height=38, fg_color="#0f1117", border_color="#2a3042",
            button_color="#00e5ff", button_hover_color="#00b8cc",
            dropdown_fg_color="#161b27", font=ctk.CTkFont(size=13),
            command=self._on_estado_change)
        self.combo_estado.set("Santa Catarina")
        self.combo_estado.pack(**pad)

        ctk.CTkLabel(side, text="CIDADES", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").pack(anchor="w", padx=18, pady=(4,4))
        self.txt_cidades = ctk.CTkTextbox(side, height=90, width=220, fg_color="#0f1117",
            border_color="#2a3042", border_width=1, font=ctk.CTkFont(size=12), text_color="#c9d1e0")
        self.txt_cidades.pack(**pad)

        ctk.CTkLabel(side, text="TERMOS DE BUSCA", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").pack(anchor="w", padx=18, pady=(4,4))
        self.txt_termos = ctk.CTkTextbox(side, height=80, width=220, fg_color="#0f1117",
            border_color="#2a3042", border_width=1, font=ctk.CTkFont(size=12), text_color="#c9d1e0")
        self.txt_termos.pack(**pad)
        for t in TERMOS_PADRAO:
            self.txt_termos.insert("end", t+"\n")

        ctk.CTkFrame(side, height=1, fg_color="#2a3042").pack(fill="x", padx=18, pady=10)
        self.lbl_total   = self._stat_label(side, "0", "empresas encontradas")
        self.lbl_com_tel = self._stat_label(side, "0", "com telefone")

        self.btn_iniciar = ctk.CTkButton(side, text="▶  Iniciar Busca", height=42, width=220,
            fg_color="#00e5ff", hover_color="#00b8cc", text_color="#0f1117",
            font=ctk.CTkFont(size=14, weight="bold"), corner_radius=8, command=self._iniciar)
        self.btn_iniciar.pack(padx=18, pady=(4,6))

        self.btn_parar = ctk.CTkButton(side, text="■  Parar", height=36, width=220,
            fg_color="#1e2535", hover_color="#2a3042", text_color="#ff4d6d",
            font=ctk.CTkFont(size=13), corner_radius=8, command=self._parar, state="disabled")
        self.btn_parar.pack(padx=18, pady=(0,6))

        self.btn_exportar = ctk.CTkButton(side, text="💾  Exportar CSV", height=36, width=220,
            fg_color="#1e2535", hover_color="#2a3042", text_color="#00e5ff",
            font=ctk.CTkFont(size=13), corner_radius=8, command=self._exportar)
        self.btn_exportar.pack(padx=18, pady=(0,6))

        self.btn_pdf = ctk.CTkButton(side, text="📄  Gerar PDF", height=36, width=220,
            fg_color="#1e2535", hover_color="#2a3042", text_color="#ff9f43",
            font=ctk.CTkFont(size=13), corner_radius=8, command=self._gerar_pdf)
        self.btn_pdf.pack(padx=18, pady=(0,6))

        self.btn_ver_pdf = ctk.CTkButton(side, text="👁  Ver PDF", height=36, width=220,
            fg_color="#1e2535", hover_color="#2a3042", text_color="#a29bfe",
            font=ctk.CTkFont(size=13), corner_radius=8, command=self._ver_pdf)
        self.btn_ver_pdf.pack(padx=18, pady=(0,18))

        self._on_estado_change("Santa Catarina")

    def _stat_label(self, parent, valor, label):
        frame = ctk.CTkFrame(parent, fg_color="#0f1117", corner_radius=8)
        frame.pack(fill="x", padx=18, pady=(0,6))
        lbl = ctk.CTkLabel(frame, text=valor,
            font=ctk.CTkFont(family="Courier New", size=26, weight="bold"), text_color="#00e5ff")
        lbl.pack(anchor="w", padx=12, pady=(8,0))
        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=11),
                     text_color="#8892a4").pack(anchor="w", padx=12, pady=(0,8))
        return lbl

    def _build_main(self, parent):
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)
        main.columnconfigure(0, weight=1)

        tab_container = ctk.CTkFrame(main, fg_color="#161b27", corner_radius=12)
        tab_container.grid(row=0, column=0, sticky="nsew", pady=(0,12))
        tab_container.rowconfigure(1, weight=1)
        tab_container.columnconfigure(0, weight=1)

        nav_bar = ctk.CTkFrame(tab_container, fg_color="#0f1117", corner_radius=0, height=52)
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_propagate(False)

        abas_def = [
            ("progresso",  "⚡  Progresso"),
            ("resultados", "🔍  Resultados"),
            ("dashboard",  "📊  Dashboard"),
            ("historico",  "📋  Histórico"),
            ("config",     "⚙  Configuração"),
        ]

        btn_frame = ctk.CTkFrame(nav_bar, fg_color="transparent")
        btn_frame.pack(side="left", padx=12, pady=8)
        for key, label in abas_def:
            b = ctk.CTkButton(btn_frame, text=label, height=34, width=130,
                fg_color="#1e2535", hover_color="#2a3042", text_color="#8892a4",
                font=ctk.CTkFont(size=12, weight="bold"), corner_radius=8,
                command=lambda k=key: self._trocar_aba(k))
            b.pack(side="left", padx=4)
            self._abas_btns[key] = b

        content = ctk.CTkFrame(tab_container, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0,4))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        for key, _ in abas_def:
            f = ctk.CTkFrame(content, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nsew")
            f.rowconfigure(0, weight=1)
            f.columnconfigure(0, weight=1)
            self._abas_frames[key] = f

        self._build_aba_resultados(self._abas_frames["resultados"])
        self._build_aba_historico(self._abas_frames["historico"])
        self._build_aba_dashboard(self._abas_frames["dashboard"])
        self._build_aba_progresso(self._abas_frames["progresso"])
        self._build_aba_config(self._abas_frames["config"])

        self.progress = ctk.CTkProgressBar(main, height=8, corner_radius=4,
                                           fg_color="#1e2535", progress_color="#00e5ff")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0,0))
        self.progress.set(0)

        self._trocar_aba("resultados")

    def _build_aba_resultados(self, parent):
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.rowconfigure(2, weight=1); wrapper.columnconfigure(0, weight=1)

        filtro_frame = ctk.CTkFrame(wrapper, fg_color="#1e2535", corner_radius=8, height=40)
        filtro_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=(4,2))
        filtro_frame.grid_propagate(False)
        ctk.CTkLabel(filtro_frame, text="🔍", font=ctk.CTkFont(size=14),
                     text_color="#8892a4").pack(side="left", padx=(10,4))
        ctk.CTkEntry(filtro_frame, textvariable=self._filtro_var,
                     placeholder_text="Filtrar por nome, telefone ou endereço...",
                     fg_color="transparent", border_width=0,
                     font=ctk.CTkFont(size=12), text_color="#c9d1e0",
                     height=34).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(filtro_frame, text="✕", width=28, height=26,
                      fg_color="transparent", hover_color="#2a3042", text_color="#8892a4",
                      font=ctk.CTkFont(size=12),
                      command=lambda: self._filtro_var.set("")).pack(side="right", padx=6)

        header = ctk.CTkFrame(wrapper, fg_color="#1e2535", corner_radius=0, height=34)
        header.grid(row=1, column=0, sticky="ew", padx=4)
        header.grid_propagate(False)
        for col, w in COLUNAS:
            ctk.CTkLabel(header, text=col, width=w,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#8892a4", anchor="w").pack(side="left", padx=8)
        ctk.CTkLabel(header, text="CONTATO", width=80,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4", anchor="center").pack(side="right", padx=18)

        self.scroll_resultados = ctk.CTkScrollableFrame(wrapper, fg_color="transparent", corner_radius=0)
        self.scroll_resultados.grid(row=2, column=0, sticky="nsew", padx=4)

    def _build_aba_historico(self, parent):
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.rowconfigure(2, weight=1); wrapper.columnconfigure(0, weight=1)

        topo = ctk.CTkFrame(wrapper, fg_color="transparent", height=40)
        topo.grid(row=0, column=0, sticky="ew", pady=(4,2))
        topo.grid_propagate(False)
        ctk.CTkLabel(topo, text="Buscas anteriores salvas automaticamente",
                     font=ctk.CTkFont(size=12), text_color="#8892a4").pack(side="left", padx=8)
        ctk.CTkButton(topo, text="🗑  Limpar histórico", height=30, width=160,
                      fg_color="#1e2535", hover_color="#2a3042", text_color="#ff4d6d",
                      font=ctk.CTkFont(size=11), corner_radius=6,
                      command=self._limpar_historico).pack(side="right", padx=8)

        hist_header = ctk.CTkFrame(wrapper, fg_color="#1e2535", corner_radius=0, height=34)
        hist_header.grid(row=1, column=0, sticky="ew", padx=4)
        hist_header.grid_propagate(False)
        for txt, w in [("DATA",160),("SEGMENTO",200),("ESTADO",160),
                       ("EMPRESAS",100),("C/ TELEFONE",110),("AÇÕES",220)]:
            ctk.CTkLabel(hist_header, text=txt, width=w,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#8892a4", anchor="w").pack(side="left", padx=8)

        scroll_outer = ctk.CTkFrame(wrapper, fg_color="#161b27", corner_radius=0)
        scroll_outer.grid(row=2, column=0, sticky="nsew", padx=4)
        self.scroll_historico = ctk.CTkScrollableFrame(scroll_outer, fg_color="transparent", corner_radius=0)
        self.scroll_historico.pack(fill="both", expand=True)
        self._renderizar_historico()

    def _build_aba_dashboard(self, parent):
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        self.dash_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.dash_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=8)
        self._renderizar_dashboard()

    def _build_aba_progresso(self, parent):
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=8)
        scroll.columnconfigure(0, weight=1)
        self._prog_scroll = scroll

        cards_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(0,16))
        for i in range(4): cards_frame.columnconfigure(i, weight=1, uniform="pc")

        def _make_card(parent, col, titulo, valor_inicial, cor):
            f = ctk.CTkFrame(parent, fg_color="#161b27", corner_radius=10)
            f.grid(row=0, column=col, sticky="nsew", padx=5)
            ctk.CTkLabel(f, text=titulo, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#8892a4").pack(anchor="w", padx=14, pady=(12,2))
            lbl = ctk.CTkLabel(f, text=valor_inicial,
                               font=ctk.CTkFont(family="Courier New", size=28, weight="bold"),
                               text_color=cor)
            lbl.pack(anchor="w", padx=14, pady=(0,12))
            return lbl

        self._lbl_prog_status    = _make_card(cards_frame, 0, "STATUS",       "Aguardando", "#8892a4")
        self._lbl_prog_tempo     = _make_card(cards_frame, 1, "TEMPO",        "00:00",      "#00e5ff")
        self._lbl_prog_vel       = _make_card(cards_frame, 2, "VELOCIDADE",   "0 / min",    "#ff9f43")
        self._lbl_prog_cidade_at = _make_card(cards_frame, 3, "CIDADE ATUAL", "—",          "#a29bfe")

        geral_frame = ctk.CTkFrame(scroll, fg_color="#161b27", corner_radius=10)
        geral_frame.grid(row=1, column=0, sticky="ew", pady=(0,14))
        geral_frame.columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(geral_frame, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(14,6))
        top_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(top_row, text="PROGRESSO GERAL",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").grid(row=0, column=0, sticky="w")
        self._lbl_prog_geral_pct = ctk.CTkLabel(top_row, text="0 / 0 cidades",
                                                font=ctk.CTkFont(size=11), text_color="#5c6478")
        self._lbl_prog_geral_pct.grid(row=0, column=1, sticky="e")

        self._prog_geral_bar = ctk.CTkProgressBar(geral_frame, height=16, corner_radius=8,
                                                  fg_color="#2a3042", progress_color="#00e5ff")
        self._prog_geral_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0,14))
        self._prog_geral_bar.set(0)

        ctk.CTkLabel(scroll, text="EMPRESAS POR CIDADE",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").grid(row=2, column=0, sticky="w", pady=(0,6))

        self._prog_cidades_frame = ctk.CTkFrame(scroll, fg_color="#161b27", corner_radius=10)
        self._prog_cidades_frame.grid(row=3, column=0, sticky="ew")
        self._prog_cidades_frame.columnconfigure(0, weight=1)

        self._lbl_prog_vazio = ctk.CTkLabel(
            self._prog_cidades_frame,
            text="⚡  Inicie uma busca para ver o progresso em tempo real.",
            font=ctk.CTkFont(size=13), text_color="#3a4252")
        self._lbl_prog_vazio.pack(pady=40)

    def _build_aba_config(self, parent):
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=8)
        scroll.columnconfigure(0, weight=1)

        MSG_PADRAO = ("Olá, {nome}! 👋\n\nVi que vocês trabalham com {segmento} e gostaria de "
                      "apresentar uma solução que pode ajudar muito o seu negócio.\n\n"
                      "Podemos conversar alguns minutos?")

        sec1 = ctk.CTkFrame(scroll, fg_color="#161b27", corner_radius=12)
        sec1.grid(row=0, column=0, sticky="ew", pady=(0,12), padx=4)
        sec1.columnconfigure(0, weight=1)

        hm = ctk.CTkFrame(sec1, fg_color="transparent")
        hm.grid(row=0, column=0, sticky="ew", padx=16, pady=(14,4))
        hm.columnconfigure(0, weight=1)
        ctk.CTkLabel(hm, text="✉  MENSAGEM PADRÃO",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").grid(row=0, column=0, sticky="w")
        self.lbl_salvo = ctk.CTkLabel(hm, text="", font=ctk.CTkFont(size=11), text_color="#00e5ff")
        self.lbl_salvo.grid(row=0, column=1, sticky="e", padx=(0,8))
        ctk.CTkButton(hm, text="💾  Salvar", width=100, height=30,
                      fg_color="#25D366", hover_color="#1da851", text_color="white",
                      font=ctk.CTkFont(size=12, weight="bold"), corner_radius=8,
                      command=self._salvar_msg_wa).grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(sec1, text="Use {nome} para o nome da empresa e {segmento} para o segmento.",
                     font=ctk.CTkFont(size=11), text_color="#5c6478").grid(
                     row=1, column=0, sticky="w", padx=16, pady=(0,8))
        self.txt_msg_wa = ctk.CTkTextbox(sec1, height=160, fg_color="#0f1117",
            border_color="#2a3042", border_width=1, font=ctk.CTkFont(size=13),
            text_color="#c9d1e0", wrap="word")
        self.txt_msg_wa.grid(row=2, column=0, sticky="ew", padx=16, pady=(0,14))
        self.txt_msg_wa.insert("1.0", MSG_PADRAO)

        sec2 = ctk.CTkFrame(scroll, fg_color="#161b27", corner_radius=12)
        sec2.grid(row=1, column=0, sticky="ew", pady=(0,12), padx=4)
        sec2.columnconfigure(1, weight=1)
        ctk.CTkLabel(sec2, text="🔭  PREVIEW DO LINK",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").grid(row=0, column=0, columnspan=3,
                                                sticky="w", padx=16, pady=(14,8))

        for row_i, (lbl, attr, ph) in enumerate([
            ("Nome da empresa:", "entry_prev_nome", "ex: Gráfica ABC"),
            ("Número (dígitos):", "entry_prev_num",  "ex: 47999998888"),
        ], start=1):
            ctk.CTkLabel(sec2, text=lbl, font=ctk.CTkFont(size=12),
                         text_color="#8892a4").grid(row=row_i, column=0, sticky="w",
                                                    padx=16, pady=(0,8))
            e = ctk.CTkEntry(sec2, width=240, height=34, fg_color="#0f1117",
                border_color="#2a3042", border_width=1, font=ctk.CTkFont(size=12),
                text_color="#c9d1e0", placeholder_text=ph)
            e.grid(row=row_i, column=1, sticky="w", padx=(0,16), pady=(0,8))
            setattr(self, attr, e)

        btn_row = ctk.CTkFrame(sec2, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(0,14))
        ctk.CTkButton(btn_row, text="📋  Copiar link", height=34, width=150,
                      fg_color="#1e2535", hover_color="#2a3042", text_color="#00e5ff",
                      font=ctk.CTkFont(size=12), corner_radius=8,
                      command=self._copiar_link_wa).pack(side="left", padx=(4,8))
        ctk.CTkButton(btn_row, text="💬  Testar no WhatsApp", height=34, width=190,
                      fg_color="#25D366", hover_color="#1da851", text_color="white",
                      font=ctk.CTkFont(size=12, weight="bold"), corner_radius=8,
                      command=self._testar_wa).pack(side="left")

        sec3 = ctk.CTkFrame(scroll, fg_color="#161b27", corner_radius=12)
        sec3.grid(row=2, column=0, sticky="ew", pady=(0,12), padx=4)
        sec3.columnconfigure(0, weight=1)
        ctk.CTkLabel(sec3, text="💡  VARIÁVEIS DISPONÍVEIS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").grid(row=0, column=0, sticky="w", padx=16, pady=(14,8))
        for i, (var, desc) in enumerate([
            ("{nome}",     "Nome da empresa extraída do Google Maps"),
            ("{segmento}", "Segmento atual definido na sidebar"),
        ]):
            ln = ctk.CTkFrame(sec3, fg_color="#0f1117" if i%2==0 else "#13181f", corner_radius=6)
            ln.grid(row=i+1, column=0, sticky="ew", padx=12, pady=2)
            ln.columnconfigure(1, weight=1)
            ctk.CTkLabel(ln, text=var,
                         font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                         text_color="#00e5ff", width=120, anchor="w").grid(
                         row=0, column=0, padx=12, pady=8)
            ctk.CTkLabel(ln, text=desc, font=ctk.CTkFont(size=12),
                         text_color="#8892a4", anchor="w").grid(
                         row=0, column=1, sticky="w", padx=(0,12), pady=8)
        ctk.CTkFrame(sec3, height=1, fg_color="transparent").grid(row=3, column=0, pady=6)

    # ── Progresso callbacks ───────────────────────────────────────────────────
    def _prog_reset(self, cidades):
        self._prog_inicio     = time.time()
        self._prog_cidades    = {c: {"encontradas": 0, "done": False} for c in cidades}
        self._prog_velocidade = []
        self._prog_cidade_refs= {}

        for w in self._prog_cidades_frame.winfo_children():
            w.destroy()

        total = len(cidades)
        for i, cidade in enumerate(cidades):
            cor_bg = "#0f1117" if i % 2 == 0 else "#13181f"
            row = ctk.CTkFrame(self._prog_cidades_frame, fg_color=cor_bg, corner_radius=6)
            row.pack(fill="x", padx=8, pady=3)
            row.columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=cidade, width=160, anchor="w",
                         font=ctk.CTkFont(size=12), text_color="#8892a4"
                         ).grid(row=0, column=0, padx=(14,8), pady=10, sticky="w")
            bar = ctk.CTkProgressBar(row, height=12, corner_radius=6,
                                     fg_color="#2a3042", progress_color="#2a3042")
            bar.grid(row=0, column=1, sticky="ew", padx=(0,12), pady=10)
            bar.set(0)
            lbl_n = ctk.CTkLabel(row, text="—", width=60, anchor="e",
                                 font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                                 text_color="#5c6478")
            lbl_n.grid(row=0, column=2, padx=(0,8), pady=10)
            lbl_st = ctk.CTkLabel(row, text="—", width=28, anchor="center",
                                  font=ctk.CTkFont(size=14), text_color="#5c6478")
            lbl_st.grid(row=0, column=3, padx=(0,14), pady=10)
            self._prog_cidade_refs[cidade] = {"bar": bar, "lbl_n": lbl_n, "lbl_st": lbl_st}

        self._lbl_prog_status.configure(text="Buscando…", text_color="#ff9f43")
        self._lbl_prog_tempo.configure(text="00:00", text_color="#00e5ff")
        self._lbl_prog_vel.configure(text="0 / min", text_color="#ff9f43")
        self._lbl_prog_cidade_at.configure(text="—", text_color="#a29bfe")
        self._lbl_prog_geral_pct.configure(text=f"0 / {total} cidades")
        self._prog_geral_bar.configure(progress_color="#00e5ff")
        self._prog_geral_bar.set(0)
        self._tick_tempo()

    def _tick_tempo(self):
        if not self.rodando or self._prog_inicio is None:
            if not self.rodando and self._prog_inicio is not None:
                elapsed = int(time.time() - self._prog_inicio)
                m, s = divmod(elapsed, 60)
                self._lbl_prog_tempo.configure(text=f"{m:02d}:{s:02d}")
            return
        elapsed = int(time.time() - self._prog_inicio)
        m, s    = divmod(elapsed, 60)
        self._lbl_prog_tempo.configure(text=f"{m:02d}:{s:02d}")
        agora   = time.time()
        recente = [t for t in self._prog_velocidade if agora - t <= 60]
        self._prog_velocidade = recente
        self._lbl_prog_vel.configure(text=f"{len(recente)} / min")
        self.after(1000, self._tick_tempo)

    def _prog_on_cidade_start(self, cidade, total_cidades, idx):
        def _up():
            refs = self._prog_cidade_refs.get(cidade)
            if refs:
                refs["bar"].configure(progress_color="#ff9f43")
                refs["bar"].set(0.05)
                refs["lbl_st"].configure(text="⏳", text_color="#ff9f43")
            self._lbl_prog_cidade_at.configure(text=cidade)
            done = sum(1 for c in self._prog_cidades.values() if c["done"])
            self._lbl_prog_geral_pct.configure(text=f"{done} / {total_cidades} cidades")
            self._prog_geral_bar.set(done / total_cidades if total_cidades else 0)
        self.after(0, _up)

    def _prog_on_cidade_found(self, cidade, total_global):
        def _up():
            self._prog_velocidade.append(time.time())
            self._prog_cidades[cidade]["encontradas"] += 1
            n    = self._prog_cidades[cidade]["encontradas"]
            refs = self._prog_cidade_refs.get(cidade)
            if refs:
                refs["lbl_n"].configure(text=str(n), text_color="#00e5ff")
                import math
                pct = min(math.log1p(n) / math.log1p(30), 1.0)
                refs["bar"].configure(progress_color="#ff9f43")
                refs["bar"].set(pct)
        self.after(0, _up)

    def _prog_on_cidade_done(self, cidade):
        total_cidades = len(self._prog_cidades)
        def _up():
            self._prog_cidades[cidade]["done"] = True
            refs = self._prog_cidade_refs.get(cidade)
            if refs:
                refs["bar"].configure(progress_color="#00e5ff")
                refs["bar"].set(1.0)
                refs["lbl_st"].configure(text="✓", text_color="#00e5ff")
                refs["lbl_n"].configure(text=str(self._prog_cidades[cidade]["encontradas"]),
                                        text_color="#00e5ff")
            done = sum(1 for c in self._prog_cidades.values() if c["done"])
            self._lbl_prog_geral_pct.configure(text=f"{done} / {total_cidades} cidades")
            self._prog_geral_bar.set(done / total_cidades if total_cidades else 0)
        self.after(0, _up)

    def _prog_finalizar(self):
        def _up():
            self._lbl_prog_status.configure(text="Concluído ✓", text_color="#00e5ff")
            self._lbl_prog_cidade_at.configure(text="—")
            self._prog_geral_bar.configure(progress_color="#00e5ff")
            self._prog_geral_bar.set(1.0)
        self.after(0, _up)

    # ── Renderizações ─────────────────────────────────────────────────────────
    def _renderizar_historico(self):
        for w in self.scroll_historico.winfo_children(): w.destroy()
        if not self.historico:
            ctk.CTkLabel(self.scroll_historico,
                         text="Nenhuma busca salva ainda.\nRealize uma busca para que ela apareça aqui.",
                         font=ctk.CTkFont(size=13), text_color="#3a4252",
                         justify="center").pack(pady=40)
            return
        for i, item in enumerate(reversed(self.historico)):
            idx    = len(self.historico) - 1 - i
            cor_bg = "#0f1117" if i % 2 == 0 else "#13181f"
            row    = ctk.CTkFrame(self.scroll_historico, fg_color=cor_bg, corner_radius=4, height=40)
            row.pack(fill="x", pady=1); row.pack_propagate(False)
            for txt, w, cor in [
                (item.get("data",""),       160, "#8892a4"),
                (item.get("segmento",""),   200, "#c9d1e0"),
                (item.get("estado",""),     160, "#c9d1e0"),
                (str(item.get("total",0)),  100, "#00e5ff"),
                (str(item.get("com_tel",0)),110, "#00e5ff"),
            ]:
                ctk.CTkLabel(row, text=txt, width=w, anchor="w",
                             font=ctk.CTkFont(size=11), text_color=cor).pack(side="left", padx=8)
            acoes = ctk.CTkFrame(row, fg_color="transparent")
            acoes.pack(side="left", padx=4)
            for txt, cor, cmd in [
                ("👁 Ver",  "#a29bfe", lambda it=item: self._ver_resultados_historico(it)),
                ("📥 CSV",  "#00e5ff", lambda it=item: self._exportar_historico_csv(it)),
                ("📄 PDF",  "#ff9f43", lambda it=item: self._exportar_historico_pdf(it)),
                ("🗑",       "#ff4d6d", lambda ix=idx:  self._deletar_historico(ix)),
            ]:
                ctk.CTkButton(acoes, text=txt, width=58 if txt != "🗑" else 30, height=26,
                              fg_color="#1e2535", hover_color="#2a3042", text_color=cor,
                              font=ctk.CTkFont(size=10), corner_radius=4,
                              command=cmd).pack(side="left", padx=2)

    def _renderizar_dashboard(self):
        for w in self.dash_frame.winfo_children(): w.destroy()
        if not self.resultados:
            ctk.CTkLabel(self.dash_frame,
                         text="📊  Realize uma busca para ver as estatísticas aqui.",
                         font=ctk.CTkFont(size=13), text_color="#3a4252").pack(pady=40)
            return
        total   = len(self.resultados)
        com_tel = sum(1 for r in self.resultados if r.get("Telefone"))
        sem_tel = total - com_tel
        pct_tel = int(com_tel/total*100) if total else 0

        cards = ctk.CTkFrame(self.dash_frame, fg_color="transparent")
        cards.pack(fill="x", pady=(8,16), padx=8)
        for i in range(4): cards.columnconfigure(i, weight=1, uniform="card")
        for col, (val, lbl, cor) in enumerate([
            (str(total),    "total de empresas", "#00e5ff"),
            (str(com_tel),  "com telefone",      "#00e5ff"),
            (str(sem_tel),  "sem telefone",      "#ff9f43"),
            (f"{pct_tel}%", "têm contato",       "#a29bfe"),
        ]):
            f = ctk.CTkFrame(cards, fg_color="#161b27", corner_radius=10)
            f.grid(row=0, column=col, sticky="nsew", padx=6)
            ctk.CTkLabel(f, text=val,
                         font=ctk.CTkFont(family="Courier New", size=32, weight="bold"),
                         text_color=cor).pack(pady=(14,2))
            ctk.CTkLabel(f, text=lbl, font=ctk.CTkFont(size=11),
                         text_color="#8892a4").pack(pady=(0,14))

        ctk.CTkLabel(self.dash_frame, text="COBERTURA DE TELEFONE",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#8892a4").pack(anchor="w", padx=14, pady=(4,6))
        cob = ctk.CTkFrame(self.dash_frame, fg_color="#161b27", corner_radius=10)
        cob.pack(fill="x", padx=8, pady=(0,16))
        pct = com_tel/total if total else 0
        cor_bar = "#00e5ff" if pct>=0.5 else "#ff9f43"
        br = ctk.CTkFrame(cob, fg_color="transparent")
        br.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(br, text=f"{pct_tel}%",
                     font=ctk.CTkFont(family="Courier New", size=18, weight="bold"),
                     text_color=cor_bar, width=56, anchor="w").pack(side="left")
        prog = ctk.CTkProgressBar(br, height=18, corner_radius=6,
                                  fg_color="#2a3042", progress_color=cor_bar)
        prog.pack(side="left", fill="x", expand=True, padx=(8,16))
        prog.set(pct)
        ctk.CTkLabel(br, text=f"{com_tel} de {total} empresas",
                     font=ctk.CTkFont(size=11), text_color="#8892a4",
                     width=140, anchor="e").pack(side="left")

        contagem = {}
        for r in self.resultados:
            end    = r.get("Endereço","").strip()
            partes = [p.strip() for p in end.split(",") if p.strip()]
            cidade = partes[-2] if len(partes)>=3 else (partes[0] if partes else "Desconhecida")
            contagem[cidade[:40]] = contagem.get(cidade[:40], 0) + 1
        top = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:10]
        if top:
            ctk.CTkLabel(self.dash_frame, text="EMPRESAS POR CIDADE (TOP 10)",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#8892a4").pack(anchor="w", padx=14, pady=(4,6))
            cf = ctk.CTkFrame(self.dash_frame, fg_color="#161b27", corner_radius=10)
            cf.pack(fill="x", padx=8, pady=(0,16))
            mx = top[0][1]
            for i, (cidade, qtd) in enumerate(top):
                ln = ctk.CTkFrame(cf, fg_color="#0f1117" if i%2==0 else "#161b27", corner_radius=6)
                ln.pack(fill="x", padx=8, pady=2)
                ctk.CTkLabel(ln, text=cidade, font=ctk.CTkFont(size=12),
                             text_color="#c9d1e0", width=220, anchor="w").pack(
                             side="left", padx=(12,8), pady=8)
                pc = ctk.CTkProgressBar(ln, height=14, corner_radius=4,
                                        fg_color="#2a3042", progress_color="#00e5ff")
                pc.pack(side="left", fill="x", expand=True, pady=8)
                pc.set(qtd/mx)
                ctk.CTkLabel(ln, text=str(qtd),
                             font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                             text_color="#00e5ff", width=40, anchor="e").pack(
                             side="left", padx=(8,12), pady=8)

    # ── Navegação de abas ─────────────────────────────────────────────────────
    def _trocar_aba(self, key):
        self._aba_ativa.set(key)
        for k, btn in self._abas_btns.items():
            if k == key:
                btn.configure(fg_color="#00e5ff", text_color="#0f1117", hover_color="#00b8cc")
            else:
                btn.configure(fg_color="#1e2535", text_color="#8892a4", hover_color="#2a3042")
        for k, frame in self._abas_frames.items():
            if k == key: frame.tkraise()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _segmento_atual(self):
        return self.entry_segmento.get().strip() or SEGMENTO_PADRAO

    def _on_segmento_change(self, event=None):
        self.lbl_header_seg.configure(text=f"Extrator de empresas — {self._segmento_atual()}")

    def _on_estado_change(self, estado):
        self.txt_cidades.delete("1.0","end")
        for c in CIDADES_POR_ESTADO.get(estado, []):
            self.txt_cidades.insert("end", c+"\n")

    def _aplicar_filtro(self, *_):
        if self.scroll_resultados is None: return
        termo = self._filtro_var.get().lower().strip()
        for child in self.scroll_resultados.winfo_children():
            try:
                vis = (not termo) or any(
                    termo in getattr(child, a, "").lower()
                    for a in ("_nome","_tel","_end"))
                child.pack(fill="x", pady=1) if vis else child.pack_forget()
            except Exception: pass

    def _add_linha(self, reg):
        idx    = len(self.resultados) - 1
        cor_bg = "#0f1117" if idx % 2 == 0 else "#13181f"
        frame  = ctk.CTkFrame(self.scroll_resultados, fg_color=cor_bg, corner_radius=4, height=36)
        frame.pack(fill="x", pady=1)
        frame.pack_propagate(False)
        frame._nome = reg.get("Nome", "")
        frame._tel  = reg.get("Telefone", "")
        frame._end  = reg.get("Endereço", "")
        frame._reg  = reg
        frame.columnconfigure(0, minsize=380)
        frame.columnconfigure(1, minsize=220)
        frame.columnconfigure(2, weight=1)

        ctk.CTkLabel(frame, text=reg.get("Nome",""), anchor="w",
                     font=ctk.CTkFont(size=12), text_color="#c9d1e0"
                     ).grid(row=0, column=0, sticky="w", padx=8)

        tel = reg.get("Telefone","")
        tf  = ctk.CTkFrame(frame, fg_color="transparent")
        tf.grid(row=0, column=1, sticky="w", padx=4)
        if tel:
            ctk.CTkButton(tf, text="💬", width=28, height=24,
                          fg_color="#25D366", hover_color="#1da851",
                          text_color="white", font=ctk.CTkFont(size=13), corner_radius=6,
                          command=lambda t=tel, n=reg.get("Nome",""): webbrowser.open(self._wa_link(t, n))
                          ).pack(side="left", padx=(0,6))
            ctk.CTkLabel(tf, text=tel, anchor="w", font=ctk.CTkFont(size=12),
                         text_color="#00e5ff").pack(side="left")
        else:
            ctk.CTkLabel(tf, text="—", anchor="w", font=ctk.CTkFont(size=12),
                         text_color="#3a4252").pack(side="left")

        ctk.CTkLabel(frame, text=reg.get("Endereço",""), anchor="w",
                     font=ctk.CTkFont(size=12), text_color="#8892a4"
                     ).grid(row=0, column=2, sticky="w", padx=8)

        contatado = reg.get("Contatado", False)

        def _toggle_contato(r=reg, f=frame):
            r["Contatado"] = not r.get("Contatado", False)
            _atualizar_btn_check(r["Contatado"])
            self._persistir_contato()

        def _atualizar_btn_check(ativo):
            if ativo:
                btn_check.configure(text="✓", fg_color="#00e5ff",
                                    hover_color="#00b8cc", text_color="#0f1117")
                frame.configure(fg_color="#0a1f1f")
            else:
                btn_check.configure(text="○", fg_color="#1e2535",
                                    hover_color="#2a3042", text_color="#3a4252")
                frame.configure(fg_color=cor_bg)

        btn_check = ctk.CTkButton(
            frame, text="✓" if contatado else "○",
            width=36, height=26, corner_radius=6,
            fg_color="#00e5ff" if contatado else "#1e2535",
            hover_color="#00b8cc" if contatado else "#2a3042",
            text_color="#0f1117" if contatado else "#3a4252",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_toggle_contato)
        btn_check.place(relx=1.0, rely=0.5, anchor="e", x=-10)
        if contatado:
            frame.configure(fg_color="#0a1f1f")

    def _animar_progress(self):
        if not self.rodando or self.progress is None: return
        import math, random
        if not hasattr(self, '_prog_vel_atual'):
            self._prog_vel_atual = random.uniform(0.008, 0.025)
            self._prog_vel_timer = 0
        self._prog_vel_timer += 1
        if self._prog_vel_timer >= random.randint(20, 50):
            self._prog_vel_atual = random.uniform(0.005, 0.028)
            self._prog_vel_timer = 0
        atual = self.progress.get()
        self.progress.set((atual + self._prog_vel_atual) % 1.0)
        t     = time.time() * 3.0
        pulso = (math.sin(t % (2*math.pi)) + 1) / 2
        r = int(0x00 + pulso * 0xcc)
        g = int(0xe5 - pulso * 0x4c)
        cor = f"#{min(255,r):02x}{min(255,g):02x}ff"
        try: self.progress.configure(progress_color=cor)
        except Exception: pass
        self.after(30, self._animar_progress)

    def _wa_link(self, numero, nome=None):
        import urllib.parse
        nums = re.sub(r'\D','',numero)
        if not nums: return ""
        if not nums.startswith('55'): nums = '55'+nums
        msg = self.txt_msg_wa.get("1.0","end").strip()
        msg = msg.replace("{nome}", nome or "empresa").replace("{segmento}", self._segmento_atual())
        return f"https://wa.me/{nums}?text={urllib.parse.quote(msg)}"

    def _salvar_msg_wa(self):
        self.lbl_salvo.configure(text="✓ Salvo!")
        self.after(2500, lambda: self.lbl_salvo.configure(text=""))

    def _copiar_link_wa(self):
        nome = self.entry_prev_nome.get().strip() or "Empresa Exemplo"
        num  = self.entry_prev_num.get().strip()  or "47999998888"
        link = self._wa_link(num, nome)
        if link:
            self.clipboard_clear(); self.clipboard_append(link)
            Dialog(self,"success","Copiado!","Link copiado para a área de transferência.")

    def _testar_wa(self):
        nome = self.entry_prev_nome.get().strip() or "Empresa Exemplo"
        num  = self.entry_prev_num.get().strip()  or "47999998888"
        link = self._wa_link(num, nome)
        if link: webbrowser.open(link)

    # ── Busca ─────────────────────────────────────────────────────────────────
    def _iniciar(self):
        if self.rodando: return
        estado   = self.combo_estado.get()
        segmento = self._segmento_atual()
        cidades  = [c.strip() for c in self.txt_cidades.get("1.0","end").splitlines() if c.strip()]
        termos   = [t.strip() for t in self.txt_termos.get("1.0","end").splitlines() if t.strip()]

        if not cidades:
            estado_key = next((k for k in CIDADES_POR_ESTADO if k.lower()==estado.lower()), None)
            if estado_key:
                cidades = list(CIDADES_POR_ESTADO[estado_key])
            else:
                Dialog(self,"warning","Atenção",f"Estado '{estado}' não encontrado."); return
        if not cidades:
            Dialog(self,"warning","Atenção","Nenhuma cidade encontrada."); return
        if not termos:
            Dialog(self,"warning","Atenção","Adicione ao menos um termo de busca."); return

        for w in self.scroll_resultados.winfo_children(): w.destroy()
        self._filtro_var.set("")
        self.resultados.clear()
        self.lbl_total.configure(text="0")
        self.lbl_com_tel.configure(text="0")
        self.progress.set(0)
        self.stop_event.clear()
        self.rodando = True
        self.btn_iniciar.configure(state="disabled")
        self.btn_parar.configure(state="normal")
        self._on_segmento_change()
        self._animar_progress()
        self._renderizar_dashboard()
        self._prog_reset(cidades)
        self._trocar_aba("progresso")

        def on_result(reg):
            self.resultados.append(reg)
            self.after(0, lambda: self._add_linha(reg))
            self.after(0, lambda: self.lbl_total.configure(text=str(len(self.resultados))))
            ct = sum(1 for r in self.resultados if r.get("Telefone"))
            self.after(0, lambda: self.lbl_com_tel.configure(text=str(ct)))

        def on_done(ok, dados=None):
            self.rodando = False
            self.after(0, lambda: self.btn_iniciar.configure(state="normal"))
            self.after(0, lambda: self.btn_parar.configure(state="disabled"))
            self.after(0, lambda: self.progress.set(1 if ok else 0))
            self.after(0, self._prog_finalizar)
            if ok and self.resultados:
                self.after(0, self._salvar_no_historico)
                self.after(0, self._renderizar_dashboard)
                self.after(0, tocar_som)
                n  = len(self.resultados)
                ct = sum(1 for r in self.resultados if r.get("Telefone"))
                self.after(0, lambda: Dialog(self,"success","Busca concluída!",
                    f"Encontradas {n} empresa(s).\nCom telefone: {ct}"))
            elif ok and not self.resultados:
                self.after(0, lambda: Dialog(self,"warning","Nenhum resultado",
                    "A busca finalizou mas não encontrou empresas.\nTente outros termos ou cidades."))
            elif not ok:
                erro_msg = dados if isinstance(dados, str) else "Verifique o terminal para mais detalhes."
                self.after(0, lambda m=erro_msg: Dialog(self,"error","Erro na busca",
                    f"Ocorreu um erro durante a busca:\n\n{m[:200]}"))

        cbs = {
            "on_log":          lambda msg: None,
            "on_result":       on_result,
            "on_done":         on_done,
            "on_cidade_start": self._prog_on_cidade_start,
            "on_cidade_found": self._prog_on_cidade_found,
            "on_cidade_done":  self._prog_on_cidade_done,
        }
        threading.Thread(target=scrape,
            args=(estado, cidades, termos, cbs, self.stop_event), daemon=True).start()

    def _salvar_no_historico(self):
        entrada = {
            "data":       datetime.now().strftime("%d/%m/%Y %H:%M"),
            "segmento":   self._segmento_atual(),
            "estado":     self.combo_estado.get(),
            "total":      len(self.resultados),
            "com_tel":    sum(1 for r in self.resultados if r.get("Telefone")),
            "resultados": self.resultados.copy(),
        }
        self.historico.append(entrada)
        salvar_historico(self.historico)
        self._renderizar_historico()
        self._atualizar_footer()

    def _parar(self):
        self.stop_event.set(); self.rodando = False
        self._lbl_prog_status.configure(text="Interrompido", text_color="#ff4d6d")
        self.btn_parar.configure(state="disabled")
        self.btn_iniciar.configure(state="normal")

    # ── Exportação ────────────────────────────────────────────────────────────
    def _exportar(self):
        if not self.resultados:
            Dialog(self,"info","Aviso","Nenhum resultado para exportar."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
            filetypes=[("CSV","*.csv")],
            initialfile=f"{slug(self._segmento_atual())}_{self.combo_estado.get().replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["Nome","Telefone","Endereço","Site","URL Maps"],
                               extrasaction="ignore")
            w.writeheader(); w.writerows(self.resultados)
        Dialog(self,"success","Exportado!",f"Arquivo salvo em:\n{path}")

    def _gerar_pdf(self):
        if not self.resultados:
            Dialog(self,"info","Aviso","Nenhum resultado para gerar PDF."); return
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
            filetypes=[("PDF","*.pdf")],
            initialfile=f"{slug(self._segmento_atual())}_{self.combo_estado.get().replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not path: return
        ok, erro = gerar_pdf(self.resultados, self.combo_estado.get(), self._segmento_atual(), path)
        if ok:
            self.ultimo_pdf = path
            Dialog(self,"success","PDF Gerado!",f"Arquivo salvo em:\n{path}")
        else:
            Dialog(self,"error","Erro ao gerar PDF", erro)

    def _ver_pdf(self):
        if not self.resultados:
            Dialog(self,"info","Aviso","Nenhum resultado para visualizar."); return
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False); tmp.close()
        ok, erro = gerar_pdf(self.resultados, self.combo_estado.get(), self._segmento_atual(), tmp.name)
        if ok: PDFViewer(self, tmp.name)
        else:  Dialog(self,"error","Erro na visualização", erro)

    def _ver_resultados_historico(self, item):
        resultados = item.get("resultados",[])
        if not resultados:
            Dialog(self,"warning","Aviso","Nenhum dado nessa busca."); return
        for w in self.scroll_resultados.winfo_children(): w.destroy()
        self._filtro_var.set("")
        self.resultados = list(resultados)
        self.lbl_total.configure(text=str(len(self.resultados)))
        self.lbl_com_tel.configure(text=str(sum(1 for r in self.resultados if r.get("Telefone"))))
        for reg in self.resultados: self._add_linha(reg)
        self._renderizar_dashboard()
        self._trocar_aba("resultados")

    def _exportar_historico_csv(self, item):
        resultados = item.get("resultados",[])
        if not resultados:
            Dialog(self,"info","Aviso","Nenhum dado nessa busca."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
            filetypes=[("CSV","*.csv")],
            initialfile=f"{slug(item.get('segmento','busca'))}_{item.get('estado','').replace(' ','_')}.csv")
        if not path: return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["Nome","Telefone","Endereço","Site","URL Maps"],
                               extrasaction="ignore")
            w.writeheader(); w.writerows(resultados)
        Dialog(self,"success","Exportado!",f"Arquivo salvo em:\n{path}")

    def _exportar_historico_pdf(self, item):
        resultados = item.get("resultados",[])
        if not resultados:
            Dialog(self,"info","Aviso","Nenhum dado nessa busca."); return
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
            filetypes=[("PDF","*.pdf")],
            initialfile=f"{slug(item.get('segmento','busca'))}_{item.get('estado','').replace(' ','_')}.pdf")
        if not path: return
        ok, erro = gerar_pdf(resultados, item.get("estado",""), item.get("segmento",""), path)
        if ok: Dialog(self,"success","PDF Gerado!",f"Arquivo salvo em:\n{path}")
        else:  Dialog(self,"error","Erro ao gerar PDF", erro)

    def _persistir_contato(self):
        if not self.historico: return
        self.historico[-1]["resultados"] = [dict(r) for r in self.resultados]
        salvar_historico(self.historico)

    def _deletar_historico(self, idx):
        def _confirmar():
            self.historico.__delitem__(idx)
            salvar_historico(self.historico)
            self._renderizar_historico()
            self._atualizar_footer()
        Dialog(self,"confirm","Remover busca","Deseja remover esta busca do histórico?",
               on_yes=_confirmar)

    def _limpar_historico(self):
        def _confirmar():
            self.historico.clear()
            self.resultados.clear()
            self.lbl_total.configure(text="0")
            self.lbl_com_tel.configure(text="0")
            salvar_historico(self.historico)
            self._renderizar_historico()
            self._renderizar_dashboard()
            self._atualizar_footer()
        Dialog(self,"confirm","Limpar histórico",
               "Tem certeza que deseja apagar todas as buscas?",
               on_yes=_confirmar)


if __name__ == "__main__":
    app = App()
    app.mainloop()