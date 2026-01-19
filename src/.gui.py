import os
import time
import threading
from tkinter import *
from tkinter.ttk import Progressbar, Style
from tkinter.scrolledtext import ScrolledText
from tkinter import filedialog, messagebox

from .rateio import processar_rateio
from .config import carregar_config, salvar_config

class RateioGUI:
    def __init__(self, root):
        self.root = root
        root.title("Sistema de Rateio de CT-e")
        root.geometry("850x680")
        root.resizable(True, True)
        root.configure(bg="#F5F5F5")
        root.state("zoomed")

        self.v_planilha = StringVar()
        self.v_pdfs = StringVar()
        self.v_xml = StringVar()
        self.v_saida = StringVar()
        self.v_pdf_unico = BooleanVar(value=False)
        

        self.carregar_config()

        frame = Frame(root, bg="#F5F5F5", padx=20, pady=20)
        frame.pack()

        if os.path.exists(LOGO_PATH):
            img = Image.open(LOGO_PATH)
            img.thumbnail((LOGO_MAX_WIDTH, LOGO_MAX_HEIGHT))
            self.logo_img = ImageTk.PhotoImage(img)
            Label(frame, image=self.logo_img, bg="#F5F5F5").pack()

        Label(
            frame,
            text="SISTEMA DE GRAVAÇÃO DE CT-e",
            bg="#F5F5F5",
            font=("Times-Roman", 15, "bold")
        ).pack(pady=10)

        self._campo(frame, "Planilha:", self.v_planilha, self.sel_planilha)
        self._campo(frame, "Pasta PDFs:", self.v_pdfs, self.sel_pdfs)
        self._campo(frame, "Pasta XML:", self.v_xml, self.sel_xml)
        self._campo(frame, "Saída:", self.v_saida, self.sel_saida)

        Checkbutton(
            frame,
            text="Gerar saída em um único PDF",
            variable=self.v_pdf_unico,
            bg="#F5F5F5"
        ).pack(pady=5)

        self.btn_processar = Button(
            frame,
            text="INICIAR PROCESSAMENTO",
            bg="#FFA024",
            width=30,
            height=2,
            command=self.iniciar_processamento
        )
        self.btn_processar.pack(pady=10)

        style = Style()
        style.configure("Adimax.Horizontal.TProgressbar", background="#FFA024",thickness=18)

        self.progress = Progressbar(
            frame,
            length=600,
            mode="determinate",
            style="Adimax.Horizontal.TProgressbar"
        )
        self.progress.pack()

        self.log = ScrolledText(frame, width=95, height=15)
        self.log.pack(pady=10)

    def _campo(self, frame, texto, var, cmd):
        linha = Frame(frame)
        linha.pack(fill="x", pady=2)

        Label(linha, text=texto, width=15, anchor="w").pack(side="left")

        entry = Entry(linha, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)

        Button(linha, text="Selecionar", command=cmd, width=12) \
            .pack(side="left", padx=10)

    def log_msg(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def carregar_config(self):
        cfg = carregar_config()
        self.v_planilha.set(cfg.get("planilha", ""))
        self.v_pdfs.set(cfg.get("pdfs", ""))
        self.v_xml.set(cfg.get("xml", ""))
        self.v_saida.set(cfg.get("saida", ""))

    def salvar_config(self):
        salvar_config({
            "planilha": self.v_planilha.get(),
            "pdfs": self.v_pdfs.get(),
            "xml": self.v_xml.get(),
            "saida": self.v_saida.get()
        })


    def sel_planilha(self):
        self.v_planilha.set(filedialog.askopenfilename())

    def sel_pdfs(self):
        self.v_pdfs.set(filedialog.askdirectory())

    def sel_xml(self):
        self.v_xml.set(filedialog.askdirectory())

    def sel_saida(self):
        self.v_saida.set(filedialog.askdirectory())

    def iniciar_processamento(self):
        self.btn_processar.config(state="disabled")
        self.root.config(cursor="watch")
        threading.Thread(target=self.processar, daemon=True).start()

    def finalizar_processamento(self):
        duracao_bruta = calculo_tempo(self.tempo_inicial, self.tempo_final)



        duracao_formato = converter_tempo(duracao_bruta)


        self.btn_processar.config(state="normal")
        self.root.config(cursor="")
        messagebox.showinfo(
            "Concluído",
            f"Processamento finalizado com sucesso\n\nDuração total: {duracao_formato}"
        )
        self.log_msg(f'Tempo total de processamento: {duracao_formato}')
        


    def processar(self):
        self.tempo_inicial = time.time()
        total_cte = 0
        sucesso = 0
        erros_chave = 0
        erros_pdf = 0
        lista_erros_chave = []
        lista_erros_pdf = []
        cte_complemento_qtd = 0
        cte_complemento_lista = []

        self.salvar_config()

        if not self.v_planilha.get() or not self.v_pdfs.get() or not self.v_saida.get():
            messagebox.showerror("Erro", "Campos obrigatórios não preenchidos.")
            return
        # =====================================================
        # INDEXAÇÃO DE XMLs (NÚMERO CT-e → CHAVE)
        # =====================================================
        mapa_cte = {}

        if self.v_xml.get():
            for nome in os.listdir(self.v_xml.get()):
                if not nome.lower().endswith(".xml"):
                    continue

                chave = extract_chave_from_xml_filename(nome)
                if not chave or not chave_cte(chave):
                    continue

                numero = extract_cte_number_from_chave(chave)
                if numero:
                    mapa_cte[numero.lstrip("0")] = chave

        

        self.log_msg(f"📌 XMLs indexados: {len(mapa_cte)}")
        # =====================================================

        if self.v_xml.get():
            renomear_pdfs_para_xmls(self.v_xml.get(), self.v_pdfs.get(), self.log_msg)

        split_temp = os.path.join(self.v_pdfs.get(), "_split_temp")
        pdf_unico_writer = PdfWriter() if self.v_pdf_unico.get() else None

        for pdf in os.listdir(self.v_pdfs.get()):
            if pdf.lower().endswith(".pdf"):
                caminho = os.path.join(self.v_pdfs.get(), pdf)
                try:
                    if len(PdfReader(caminho).pages) > 1:
                        split_pdf_por_cte(caminho, split_temp, self.log_msg)
                    if os.path.isdir(split_temp):
                        for nome in os.listdir(self.v_pdfs.get()):
                            if nome.lower().endswith(".pdf") and "-procCTe" in nome:
                                origem = os.path.join(self.v_pdfs.get(), nome)
                                destino = os.path.join(split_temp, nome)
                                if not os.path.exists(destino):
                                    shutil.copy(origem, destino)
                except:
                    pass

        pdf_base = split_temp if os.path.isdir(split_temp) else self.v_pdfs.get()

        df = pd.read_excel(self.v_planilha.get())
        grupos = df.groupby("N° CT-e")
        total_cte = len(grupos)
        self.progress["maximum"] = total_cte

        for i, (ncte, grupo) in enumerate(grupos, start=1):
            self.progress["value"] = i

            chave_cte_encontrada = None

            ncte_str = str(int(ncte))

            chave_cte_encontrada = mapa_cte.get(ncte_str)

            if not chave_cte_encontrada:
                erros_chave += 1 
                lista_erros_chave.append({
                    'CT-e': ncte_str,
                    'Motivo': 'Chave não encontrada'
                })
                self.log_msg(f'Chave não encontrada para o CT-e {ncte_str}')
                continue

            pdf = localizar_pdf(pdf_base, chave_cte_encontrada)

            if not pdf:
                erros_pdf +=1

                lista_erros_pdf.append({
                    'CT-e': ncte_str,
                    'Motivo': 'PDF não encontrado'
                })

                self.log_msg(f"❌ PDF não encontrado para chave {chave_cte_encontrada}")
                continue

            reader = PdfReader(pdf)
            
            texto_primeira_pagina = reader.pages[0].extract_text()
            if verificar_complemento(texto_primeira_pagina):
                cte_complemento_qtd += 1

                cte_complemento_lista.append({
                    'CT-e': ncte_str,
                    'Arquivo': os.path.basename(pdf)
                })

                self.log_msg(f'ℹ️ CT-e {ncte_str} identificado como COMPLEMENTO')

            linhas = []

            valores = []

            xml_path = localizar_xml_por_chave(chave_cte_encontrada, self.v_xml.get())
            
            valor_cte = extrair_valor_total_cte(xml_path) if os.path.exists(xml_path) else None

            for _, r in grupo.iterrows():
                base = converter_moeda_para_decimal(r.get("Vlr Contabil"))
                if not base or base <= 0:
                    continue

                base = base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                prefixo = identificar_prefixo_oper(str(r.get("Operação", "")))
                if not prefixo:
                    continue
                

                linhas.append({'prefixo': prefixo,
                               'valor': base})
                
                valores.append(base)
            
            if valor_cte:
                soma_comparacao = sum(valores).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                diferenca = (valor_cte - soma_comparacao).quantize(Decimal("0.01"))

                if diferenca != Decimal("0.00"):
                    if abs(diferenca) <= Decimal("0.01"):
                        linha_menor = min(linhas, key=lambda x: x["valor"])

                        valor_original = linha_menor["valor"]
                        linha_menor["valor"] += diferenca

                        self.log_msg(
                            f"⚠️ Ajuste por arredondamento no CT-e {ncte_str}: "
                            f"{formato_brl(diferenca)} aplicado na menor linha "
                            f"({linha_menor['prefixo']} | "
                            f"{formato_brl(valor_original)} → "
                            f"{formato_brl(linha_menor['valor'])})"
                        )
                    else:
                        self.log_msg(
                            f"❌ Divergência relevante no CT-e {ncte_str}"
                            f"{formato_brl(diferenca)}"
                        )
                        continue

            texto_overlay = [
                f"{l['prefixo']}: R$ {formato_brl(
                    l['valor'].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                )}"
                for l in linhas
            ]

            if not linhas:
                continue

            overlay = os.path.join(self.v_saida.get(), f"{ncte}_overlay.pdf")
            saida = os.path.join(
                self.v_saida.get(),
                os.path.basename(pdf).replace(".pdf", "_rateado.pdf")
            )

            criar_overlay("\n".join(texto_overlay), overlay)

            if self.v_pdf_unico.get():
                sobrepor_pdf(pdf, overlay, saida)
                reader_temp = PdfReader(saida)
                for p in reader_temp.pages:
                    pdf_unico_writer.add_page(p)
            else:
                sobrepor_pdf(pdf, overlay, saida)

            if self.v_pdf_unico.get() and pdf_unico_writer:
                caminho_final = os.path.join(
                    self.v_saida.get(),
                    "CTE_RATEIO_UNIFICADO.pdf"
                )
                with open(caminho_final, "wb") as f:
                    pdf_unico_writer.write(f)

                self.log_msg(
                    f"📄 PDF único gerado → {os.path.basename(caminho_final)}"
                )
            sucesso +=1
            self.log_msg(
                "✔ CT-e {} processado".format(ncte).replace(".0", "")
            )
        self.log_msg('-'*30)
        self.log_msg(f'Resumo do Processamento de Dados:')
        self.log_msg(f'Quantidade de CT-e processados: {sucesso}')
        self.log_msg(f'Quantidade de chaves não encontradas: {erros_chave}')
        self.log_msg(f'Quantidade de PDF não encontrados: {erros_pdf}')
        self.log_msg("🎉 Processamento concluído")

        if cte_complemento_qtd>0:
            self.log_msg('-'*30)
            self.log_msg(f'📌 CT-es de Complemento identificados: {cte_complemento_qtd}')

            for item in cte_complemento_lista:
                self.log_msg(f"   - CT-e {item['CT-e']} | PDF: {item['Arquivo']}")

            self.log_msg('-'*30)

        self.tempo_final = time.time()

        self.root.after(0, self.finalizar_processamento)