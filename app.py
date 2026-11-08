import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ==========================================
# SEU NEGÓCIO PRÓPRIO - CONFIGURAÇÕES OFICIAIS
# ==========================================
CARTEIRA_DESTINO_LIGHTNING = "artfulfuture85@walletofsatoshi.com"
VALOR_SERVICO_SATS = 500  # Custo padrão por transação automatizada

def gerar_fatura_lnurl(lightning_address, satoshis, memo):
    """Gera a fatura BOLT11 e a URL de verificação de pagamento."""
    try:
        if "@" not in lightning_address:
            return None, None, None
            
        nome, dominio = lightning_address.split("@")
        url_lnurl = f"https://{dominio}/.well-known/lnurlp/{nome}"
        
        resp = requests.get(url_lnurl, timeout=10)
        if resp.status_code != 200:
            return None, None, None
            
        dados = resp.json()
        callback = dados.get("callback")
        milissatoshis = satoshis * 1000
        
        inv_resp = requests.get(f"{callback}?amount={milissatoshis}&comment={memo}", timeout=10)
        inv_data = inv_resp.json()
        
        return inv_data.get("pr"), inv_data.get("verify"), inv_data.get("payment_hash")
    except Exception as e:
        print(f"Erro ao gerar fatura: {e}")
        return None, None, None

def checar_status_pagamento(verify_url):
    """Verifica se o pagamento foi liquidado na rede Lightning."""
    try:
        if not verify_url:
            return False
        resp = requests.get(verify_url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("settled", False)
        return False
    except:
        return False

# ==========================================
# INTERFACES E ROTAS DO SISTEMA
# ==========================================

HTML_HOME = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>⚡ Lightning Auto-Gateway</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #090d16; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #131d31; padding: 40px; border-radius: 16px; box-shadow: 0 15px 35px rgba(0,0,0,0.5); width: 440px; text-align: center; border: 1px solid #1e293b; }
        h2 { color: #f59e0b; margin-bottom: 10px; }
        p { color: #94a3b8; font-size: 14px; margin-bottom: 25px; }
        input { width: 100%; padding: 14px; margin: 10px 0; border-radius: 8px; border: 1px solid #334155; background: #090d16; color: white; box-sizing: border-box; font-size: 14px; }
        button { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; font-weight: bold; border: none; padding: 14px 20px; width: 100%; border-radius: 8px; cursor: pointer; margin-top: 15px; font-size: 15px; }
        button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ Auto-Gateway</h2>
        <p>Insira seu link para gerar proteção instantânea via micro-pagamento.</p>
        <form action="/processar" method="POST">
            <input type="text" name="url_destino" placeholder="https://seu-link-privado.com" required>
            <button type="submit">Proteger Link ({{ valor }} Sats)</button>
        </form>
    </div>
</body>
</html>
"""

HTML_CHECKOUT = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Aguardando Pagamento</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #090d16; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #131d31; padding: 40px; border-radius: 16px; box-shadow: 0 15px 35px rgba(0,0,0,0.5); width: 460px; text-align: center; border: 1px solid #1e293b; }
        h2 { color: #38bdf8; margin-bottom: 10px; }
        textarea { width: 100%; height: 100px; background: #090d16; color: #38bdf8; padding: 12px; border-radius: 8px; border: 1px solid #334155; font-family: monospace; resize: none; box-sizing: border-box; margin: 15px 0; font-size: 12px; }
        .status { margin-top: 15px; font-weight: bold; color: #f59e0b; }
    </style>
    <script>
        const verifyUrl = "{{ verify_url }}";
        const linkDestino = "{{ url_destino }}";

        function checarPagamento() {
            fetch('/api/checar?url=' + encodeURIComponent(verifyUrl))
                .then(res => res.json())
                .then(data => {
                    if (data.pago) {
                        document.getElementById('conteudo-card').innerHTML = `
                            <h2 style="color: #10b981;">⚡ Pagamento Confirmado!</h2>
                            <p>Seu link protegido foi liberado com sucesso:</p>
                            <input type="text" value="${linkDestino}" readonly style="width:100%; padding:12px; background:#090d16; color:#38bdf8; border:1px solid #10b981; border-radius:8px; text-align:center;" />
                            <br><br><a href="/" style="color:#94a3b8; text-decoration:underline;">Criar outro link</a>
                        `;
                    }
                });
        }
        setInterval(checarPagamento, 3000);
    </script>
</head>
<body>
    <div class="card" id="conteudo-card">
        <h2>⚡ Pagamento Pendente</h2>
        <p>Pague exatamente <b>{{ valor }} Satoshis</b> para liberar o acesso:</p>
        <textarea readonly>{{ invoice }}</textarea>
        <div class="status">🔄 Aguardando pagamento na rede...</div>
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_HOME, valor=VALOR_SERVICO_SATS)

@app.route("/processar", methods=["POST"])
def processar():
    url_destino = request.form.get("url_destino")
    memo = f"Protecao automatica de link para: {url_destino}"
    
    invoice, verify_url, p_hash = gerar_fatura_lnurl(CARTEIRA_DESTINO_LIGHTNING, VALOR_SERVICO_SATS, memo)
    if not invoice:
        return "Erro ao gerar fatura relâmpago.", 500
        
    return render_template_string(HTML_CHECKOUT, valor=VALOR_SERVICO_SATS, invoice=invoice, verify_url=verify_url, url_destino=url_destino)

@app.route("/api/checar")
def api_checar():
    verify_url = request.args.get("url")
    pago = checar_status_pagamento(verify_url)
    return jsonify({"pago": pago})

@app.route("/api/v1/criar-cobranca-automatica", methods=["POST"])
def api_criar_cobranca_automatica():
    dados = request.json
    if not dados or "url_destino" not in dados:
        return jsonify({"erro": "Parâmetro 'url_destino' é obrigatório"}), 400
        
    url_destino = dados["url_destino"]
    memo = f"Operacao automatica via API: {url_destino}"
    
    invoice, verify_url, p_hash = gerar_fatura_lnurl(CARTEIRA_DESTINO_LIGHTNING, VALOR_SERVICO_SATS, memo)
    if not invoice:
        return jsonify({"erro": "Falha ao gerar fatura Lightning"}), 500
        
    return jsonify({
        "status": "sucesso",
        "destino": CARTEIRA_DESTINO_LIGHTNING,
        "valor_sats": VALOR_SERVICO_SATS,
        "invoice_bolt11": invoice,
        "verify_url": verify_url
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
