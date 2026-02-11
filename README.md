# GEO Audit Tool 🌍🔍 v1.2.0

O **GEO Audit Tool** é uma ferramenta de linha de comando (CLI) avançada e leve em Python para auditar sites com foco em **GEO (Generative Engine Optimization)**. 

O objetivo é avaliar o quão bem um site está estruturado para ser indexado, compreendido e citado por modelos de Inteligência Artificial Generativa (como ChatGPT, Claude, Perplexity e Gemini). Ela fornece um score técnico e recomendações práticas para melhorar a visibilidade do seu conteúdo na "Era das IAs".

---

## 🚀 Funcionalidades e Pilares de Análise

O script realiza uma auditoria técnica baseada em 6 módulos fundamentais:

1.  **Acesso de Robôs (robots.txt)** 🤖
    *   Verifica permissões para bots específicos de IA (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `GoogleOther`, `Applebot-Extended`).
2.  **Estrutura & Semântica** 🏗️
    *   Valida a hierarquia de tags (H1 a H3).
    *   Analisa o uso de cabeçalhos interrogativos e "Cápsulas de Resposta" (parágrafos otimizados de 40-60 palavras).
    *   Detecta o uso de âncoras (`id`) para fragmentos de conteúdo.
3.  **Dados Estruturados (Schema.org)** 📊
    *   Identifica JSON-LD essenciais (`Organization`, `FAQPage`, `Article`, etc.).
    *   Verifica links de entidade (`sameAs`) e frescura do conteúdo.
4.  **E-E-A-T & Credibilidade** 🏅
    *   Busca por biografias de autor, densidade estatística (números e dados) e citações externas.
5.  **Tamanho da Página** 📦
    *   Analisa o peso da página para garantir que não ultrapasse limites de processamento de context-window de IAs (alerta em > 2MB).
6.  **Autoridade do Site (Scrapingdog)** 🏢
    *   Utiliza a API do Scrapingdog para verificar o número real de páginas indexadas no Google e a relevância no topo dos resultados.

---

## 🛠️ Instalação (Recomendada via Virtualenv)

Para evitar conflitos com outros pacotes do sistema, recomenda-se o uso de um ambiente virtual:

```bash
# 1. Clone o repositório ou acesse a pasta
cd geo-audit

# 2. Crie o ambiente virtual
python3 -m venv venv

# 3. Ative o ambiente virtual
# No macOS/Linux:
source venv/bin/activate
# No Windows:
# venv\Scripts\activate

# 4. Instale as dependências
pip install requests beautifulsoup4
```

---

## ⚙️ Configuração (API Scrapingdog)

Para utilizar o módulo de **Autoridade do Site**, você precisará de uma chave de API do [Scrapingdog](https://www.scrapingdog.com/).

1.  Crie um arquivo chamado `.env` na raiz do projeto.
2.  Adicione sua chave no seguinte formato:
    ```env
    SCRAPINGDOG_API_KEY=sua_chave_aqui
    ```

> [!NOTE]  
> O script possui um parser manual para o `.env`, portanto, não é necessário instalar a biblioteca `python-dotenv`.

---

## 💻 Como Usar

Com o ambiente virtual ativado, execute o script passando a URL alvo:

```bash
python3 geo-audit.py https://seu-dominio.com.br
```

### Comandos e Parâmetros

| Comando | Descrição |
| :--- | :--- |
| `python3 geo-audit.py URL` | Executa a auditoria completa com relatório formatado no terminal. |
| `--json` | Retorna o relatório em formato JSON puro (ideal para integrações). |
| `-v`, `--version`, `--versao` | Exibe a versão atual do script (`v1.2.0`). |
| `-h`, `--help` | Exibe o menu de ajuda detalhado. |

---

## 📊 Relatório e Otimização

O relatório CLI é dividido em seções coloridas para facilitar a leitura:
*   **GEO SCORE GERAL**: Uma nota de 0 a 100 ponderada pela relevância técnica para IAs.
*   **Recomendações Prioritárias**: Uma lista de tarefas gerada dinamicamente com base nas falhas encontradas na página.

---

## 🤝 Contribuição

Contribuições são bem-vindas! Se você tiver sugestões para novos bots de IA ou novos critérios de pontuaçãobaseados em pesquisas recentes de GEO, sinta-se à vontade para abrir uma issue ou PR.

---

## 📄 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
