import json
import logging
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# --- CARREGAR TODOS OS JSONs DA PASTA ---
def carregar_todos_json():
    dados_completos = []
    precos_dict = {}

    # Caminho absoluto da pasta onde está este script
    caminho_pasta = os.path.dirname(os.path.abspath(__file__))

    for arquivo in os.listdir(caminho_pasta):
        caminho_completo = os.path.join(caminho_pasta, arquivo)
        if arquivo.endswith(".json"):
            try:
                with open(caminho_completo, "r", encoding="utf-8") as f:
                    dados = json.load(f)

                # Se for lista, mantém a lógica antiga
                if isinstance(dados, list):
                    dados_completos.extend(dados)
                    for item in dados:
                        for opcao in item.get("opcoes", []):
                            nome = opcao.get("nome", "").lower()
                            valor = opcao.get("valor", 0)
                            if nome:
                                precos_dict[nome] = valor
                # Se for dicionário simples, adiciona direto no PRECOS
                elif isinstance(dados, dict):
                    for nome, valor in dados.items():
                        precos_dict[nome.lower()] = valor

            except json.JSONDecodeError as e:
                logging.error(f"JSON mal formatado em {arquivo}: {e}")
            except Exception as e:
                logging.error(f"Erro ao ler {arquivo}: {e}")

    if not dados_completos and not precos_dict:
        logging.warning("⚠️ Nenhum JSON carregado corretamente. Verifique os arquivos .json na pasta!")

    return dados_completos, precos_dict

# --- Carrega os JSONs ---
DADOS, PRECOS = carregar_todos_json()

# --- SALVAR JSON PADRÃO ---
def salvar_json_padrao():
    with open("precos.json", "w", encoding="utf-8") as f:
        json.dump(DADOS, f, indent=4, ensure_ascii=False)

# --- MENSAGEM DE BOAS-VINDAS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = (
        "🏷️ *Cellairis — Rede 2G*\n"
        "👋 *Bem-vindo(a) a nossa consulta automatica de precos — uso interno!*\n\n"
        "🔎 Para buscar digite o servico ou modelo:\n"
        "📱 `iPhone 14 Pro Max` → lista todos os servicos e pecas\n"
        "🔋 `Bateria iPhone 14` → lista todas as baterias\n"
        "🪞 `Vidro traseiro iPhone` → lista todos os vidros traseiros\n\n"
        "📊 *Calculo de MKP:*\n"
        "Use o comando `/mkp`\n"
        "Digite o valor da peca e o valor total da logistica (ida volta e entrega da peca ao tecnico) e envie um print para *Luiz* ou *Mari* para confirmacao\n\n"
        "📸 Envie tambem um print do valor do aparelho no Google para realizarmos um calculo mais assertivo ✅"
    )
    await update.message.reply_text(mensagem)

# --- BUSCA PARCIAL ---
async def buscar_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    resultados = {nome: valor for nome, valor in PRECOS.items() if texto in nome}

    if resultados:
        resposta = "💰 Encontrei os seguintes preços:\n\n"
        for nome, valor in resultados.items():
            resposta += f"- {nome.title()}: R$ {valor:.2f}\n"
        await update.message.reply_text(resposta)
    else:
        await update.message.reply_text(
            "❌ Modelo não encontrado. Certifique-se de digitar corretamente ou tente palavras-chave como nos exemplos."
        )

# --- FUNÇÃO PARA PROCESSAR LINHA DE PRODUTO ---
def processar_linha(linha):
    partes = linha.strip().split()
    opcoes = []
    nome_base = []
    i = 0
    while i < len(partes):
        if partes[i].replace(".", "", 1).isdigit():
            valor = float(partes[i])
            nome = " ".join(nome_base)
            opcoes.append({"nome": nome.strip(), "valor": valor})
            nome_base = []
        else:
            nome_base.append(partes[i])
        i += 1
    return opcoes

# --- COMANDO /ADD ---
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args).split("\n")
    adicionados = []
    for linha in texto:
        if not linha.strip():
            continue
        opcoes = processar_linha(linha)
        if not opcoes:
            continue
        modelo = opcoes[0]['nome'].split()[1] if len(opcoes[0]['nome'].split()) > 1 else "Desconhecido"
        DADOS.append({
            "codigo": f"novo-{len(DADOS)+1}",
            "modelo": modelo,
            "opcoes": opcoes
        })
        for opc in opcoes:
            PRECOS[opc['nome'].lower()] = opc['valor']
            adicionados.append(opc['nome'])
    salvar_json_padrao()
    await update.message.reply_text(f"✅ Produtos adicionados: {', '.join(adicionados)}")

# --- COMANDO /EDIT ---
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args).split("\n")
    editados = []
    for linha in texto:
        if not linha.strip():
            continue
        opcoes = processar_linha(linha)
        if not opcoes:
            continue
        modelo = opcoes[0]['nome'].split()[1] if len(opcoes[0]['nome'].split()) > 1 else "Desconhecido"
        encontrado = False
        for item in DADOS:
            if modelo.lower() in item['modelo'].lower():
                item['opcoes'] = opcoes
                encontrado = True
                break
        if encontrado:
            for opc in opcoes:
                PRECOS[opc['nome'].lower()] = opc['valor']
                editados.append(opc['nome'])
    salvar_json_padrao()
    await update.message.reply_text(f"✅ Produtos editados: {', '.join(editados)}")

# --- CÁLCULO MKP ---
CUSTO, LOGISTICA, VENDA = range(3)

async def start_mkp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💵 Envie o valor de *custo da peça*:", parse_mode="Markdown")
    return CUSTO

async def receber_custo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["custo"] = float(update.message.text.replace(",", "."))
        await update.message.reply_text("🚚 Agora envie o valor total da logística (*Ida, volta e peça do fornecedor ao técnico*):", parse_mode="Markdown")
        return LOGISTICA
    except ValueError:
        await update.message.reply_text("❌ Valor invalido. Envie apenas numeros (ex: 300.50).")
        return CUSTO

async def receber_logistica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["logistica"] = float(update.message.text.replace(",", "."))
        await update.message.reply_text("💰 Envie o *valor de venda final*:", parse_mode="Markdown")
        return VENDA
    except ValueError:
        await update.message.reply_text("❌ Valor invalido. Envie apenas numeros (ex: 50).")
        return LOGISTICA

async def receber_venda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        custo = context.user_data["custo"]
        logistica = context.user_data["logistica"]
        venda = float(update.message.text.replace(",", "."))

        royalt = venda * 0.10
        custo_total = custo + logistica + royalt
        mkp = venda / custo_total

        mkp_ideal = 3.0
        mkp_minimo = 2.5
        venda_ideal = mkp_ideal * custo_total
        venda_minima = mkp_minimo * custo_total

        resposta = (
            f"🧾 *Calculo de MKP*\n\n"
            f"💵 *Custo:* R${custo:.2f}\n"
            f"🚚 *Logistica:* R${logistica:.2f}\n"
            f"🏷️ *Royalt (10%):* R${royalt:.2f}\n"
            f"📦 *Custo total:* R${custo_total:.2f}\n\n"
            f"💰 *Venda atual:* R${venda:.2f}\n"
            f"📈 *MKP atual:* {mkp:.2f}\n\n"
        )

        if mkp >= mkp_ideal:
            resposta += "✅ *Venda boa — MKP acima de 3.0! Confirmar com Luiz ou Mari.*"
        elif mkp >= mkp_minimo:
            resposta += (
                "🟡 *Margem razoavel — quase boa!*\n"
                f"💡 Para atingir MKP ideal (3.0), venda deveria ser *R${venda_ideal:.2f}*.\n"
                "📌 Confirmar com Luiz ou Mari."
            )
        else:
            resposta += (
                "⚠️ *Margem baixa — MKP abaixo de 2.5.*\n"
                f"💡 Venda ideal para MKP 3.0: *R${venda_ideal:.2f}*\n"
                f"💡 Venda minima para MKP 2.5: *R${venda_minima:.2f}*\n"
                "📌 Confirmar com Luiz ou Mari."
            )

        await update.message.reply_text(resposta, parse_mode="Markdown")
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Valor invalido. Envie apenas numeros (ex: 800).")
        return VENDA

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Calculo cancelado.")
    return ConversationHandler.END

# --- RODAR BOT ---
if __name__ == "__main__":
    TOKEN = "8461363227:AAGoXGsKl0dM45xP7dLYcNkURcV6ywBdhkA"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("edit", edit))

    conv_handler_mkp = ConversationHandler(
        entry_points=[CommandHandler("mkp", start_mkp)],
        states={
            CUSTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_custo)],
            LOGISTICA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_logistica)],
            VENDA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_venda)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    app.add_handler(conv_handler_mkp)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_preco))

    print("🤖 Bot iniciado e pronto para uso! (Lendo todos os .json da pasta)")
    app.run_polling()
