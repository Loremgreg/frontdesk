from flask import Flask, request, Response

app = Flask(__name__)

@app.route("/voice", methods=["POST"])
def voice():
    print(" Appel entrant :", request.form)
    response = """<Response><Say language="fr-FR">Bonjour, ceci est un test de l'assistant vocal.</Say></Response>"""
    return Response(response, mimetype="text/xml")

@app.route("/sms", methods=["POST"])
def sms():
    print(" SMS reçu :", request.form)
    return Response("<Response></Response>", mimetype="text/xml")

if __name__ == "__main__":
    app.run(port=5000)
