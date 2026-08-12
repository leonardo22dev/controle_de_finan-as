r"""Gera os ícones PNG da PWA.

    ..\.venv\Scripts\python.exe gerar_icones.py

Só precisa rodar de novo se você mudar as cores ou o desenho.
Requer Pillow (`pip install pillow`) — não é dependência do bot.
"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).parent / "icons"
FUNDO = (15, 118, 110)      # #0f766e, mesmo teal do tema
BARRA = (255, 255, 255)

# Alturas relativas das barras (fração da área útil), da esquerda para a direita.
ALTURAS = [0.45, 0.70, 1.00]


def desenhar(tamanho: int, escala_conteudo: float, raio_frac: float) -> Image.Image:
    """escala_conteudo: quanto da imagem o desenho ocupa (menor = mais margem).
    raio_frac: arredondamento do quadrado (0 = quadrado, 0.5 = círculo)."""
    # Desenha em 4x e reduz — antialiasing de pobre, mas eficaz.
    s = tamanho * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * raio_frac), fill=FUNDO)

    area = s * escala_conteudo
    margem = (s - area) / 2

    n = len(ALTURAS)
    vao = area * 0.10
    largura = (area - vao * (n - 1)) / n
    base = margem + area

    for i, alt in enumerate(ALTURAS):
        x0 = margem + i * (largura + vao)
        altura = area * alt
        d.rounded_rectangle(
            [x0, base - altura, x0 + largura, base],
            radius=int(largura * 0.22),
            fill=BARRA,
        )

    return img.resize((tamanho, tamanho), Image.LANCZOS)


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)

    # Ícone normal: desenho ocupa 56%, cantos bem arredondados.
    for tam in (192, 512):
        desenhar(tam, 0.56, 0.22).save(DESTINO / f"icon-{tam}.png")
        print(f"  icons/icon-{tam}.png")

    # Maskable: o Android recorta até 20% de cada lado, então o conteúdo
    # precisa caber no círculo central. Fundo cobre tudo, desenho menor.
    desenhar(512, 0.40, 0.0).save(DESTINO / "icon-maskable-512.png")
    print("  icons/icon-maskable-512.png")


if __name__ == "__main__":
    main()
