# ExtractorPro

Aplicativo desktop para extração automática de dados empresariais do Google Maps — nome, telefone, endereço e site — com interface gráfica dark mode.

---

## Funcionalidades

- Busca por **segmento + cidade + estado** no Google Maps
- Extrai **nome, telefone/WhatsApp, endereço e site** de cada resultado
- Suporte a **múltiplas cidades e termos de busca** em uma única sessão
- Exportação para **CSV** com um clique
- **Histórico de buscas** salvo localmente
- Interface dark mode com [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- Scraper headless via [Playwright](https://playwright.dev/python/) (Chromium)
- **Instalação automática de dependências** na primeira execução

---

## Pré-requisitos

- Python 3.10+

Só isso. Na primeira vez que rodar, o programa instala tudo sozinho.

---

## Instalação

```bash
# Clone o repositório
git clone https://github.com/MatheusBonetti/ExtractorPro.git
cd ExtractorPro

# Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate
```

---

## Como usar

```bash
python ExtractorPro/app.py
```

Na primeira execução, o programa verifica e instala automaticamente:
- `customtkinter`
- `playwright`
- Chromium (navegador usado pelo scraper)

Depois é só usar:

1. Selecione o **estado** e as **cidades** desejadas
2. Informe o **segmento** (ex: `Restaurante`, `Clínica`, `Academia`)
3. Adicione os **termos de busca**
4. Clique em **Iniciar** e aguarde a extração
5. Exporte os resultados para **CSV**

---

## Estrutura do projeto

```
ExtractorPro/
├── app.py          # Aplicativo principal (GUI + scraper)
├── cidades.py      # Base de cidades por estado
└── historico.json  # Histórico de buscas (gerado em runtime)
```

---

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python | Linguagem principal |
| CustomTkinter | Interface gráfica dark mode |
| Playwright | Automação do Chromium |
| Google Maps | Fonte dos dados |

---

## Aviso

Este projeto é para fins educacionais. Respeite os [Termos de Serviço do Google](https://policies.google.com/terms) ao utilizá-lo.
