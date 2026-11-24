import base64
import json
import unittest

from hello_world import app


def evento(corpo):
    return {"body": json.dumps(corpo)}


class TestGuiaTransporte(unittest.TestCase):
    def test_sem_requisicao_id_devolve_400(self):
        resposta = app.lambda_handler(evento({"hospital": "H-Recife"}), None)
        self.assertEqual(resposta["statusCode"], 400)

    def test_com_requisicao_id_devolve_guia_201(self):
        resposta = app.lambda_handler(
            evento({"requisicaoId": "R-001", "hospital": "H-Recife", "bolsas": ["O-NEG-0142"]}), None)
        guia = json.loads(resposta["body"])
        self.assertEqual(resposta["statusCode"], 201)
        self.assertEqual(guia["guia"], "G-R-001")
        self.assertEqual(guia["bolsas"], ["O-NEG-0142"])

    def test_corpo_em_base64_como_no_evento_do_sam(self):
        corpo = base64.b64encode(json.dumps({"requisicaoId": "R-64"}).encode()).decode()
        resposta = app.lambda_handler({"body": corpo, "isBase64Encoded": True}, None)
        self.assertEqual(json.loads(resposta["body"])["guia"], "G-R-64")

    def test_contador_cresce_no_mesmo_ambiente(self):
        primeira = json.loads(app.lambda_handler(evento({"requisicaoId": "R-A"}), None)["body"])
        segunda = json.loads(app.lambda_handler(evento({"requisicaoId": "R-B"}), None)["body"])
        self.assertEqual(segunda["invocacaoNesteAmbiente"], primeira["invocacaoNesteAmbiente"] + 1)


if __name__ == "__main__":
    unittest.main()
