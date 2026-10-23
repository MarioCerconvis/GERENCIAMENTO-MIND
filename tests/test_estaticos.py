"""Sanidade dos arquivos estáticos."""
import os
import re
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class CssTest(unittest.TestCase):

    def test_chaves_balanceadas_no_css(self):
        """Uma chave sem fechar faz o navegador ignorar todo o CSS seguinte
        (já aconteceu num merge e a tela de prioridades ficou sem estilo)."""
        with open(os.path.join(RAIZ, "static", "css", "style.css"), encoding="utf-8") as f:
            css = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)
        profundidade = 0
        for n, linha in enumerate(css.split("\n"), start=1):
            profundidade += linha.count("{") - linha.count("}")
            self.assertGreaterEqual(profundidade, 0, f"'}}' sobrando na linha {n}")
        self.assertEqual(profundidade, 0, "há '{' sem fechar no style.css")


if __name__ == "__main__":
    unittest.main()
