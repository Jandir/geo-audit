# GEO Audit Tool 🌍🔍

Este projeto é uma ferramenta de linha de comando (CLI) escrita em Python para auditar e analisar sites com foco em **GEO (Generative Engine Optimization)**. Ele avalia o quão amigável um site é para motores de busca baseados em IA (como ChatGPT, Claude, Perplexity, Gemini, etc.) e fornece um relatório detalhado com uma pontuação e recomendações práticas.

## 🚀 Funcionalidades

A ferramenta realiza uma análise baseada em 4 pilares principais:

1.  **Acesso de Robôs (robots.txt)** 🤖
    *   Verifica se o `robots.txt` permite o acesso de bots de IA importantes (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `GoogleOther`, `Applebot-Extended`).
    *   Calcula o impacto das restrições na visibilidade para IAs.

2.  **Estrutura & Semântica** 🏗️
    *   **Hierarquia**: Valida a estrutura de tags H1, H2 e H3.
    *   **Perguntas**: Verifica se os cabeçalhos são formulados como perguntas (essencial para capturar intenção de busca).
    *   **Cápsulas de Resposta**: Identifica parágrafos concisos (40-60 palavras) logo após os cabeçalhos, ideais para serem citados por IAs.
    *   **Âncoras Profundas**: Checa a presença de IDs únicos em seções para permitir links diretos ("deep-linking").

3.  **Dados Estruturados (Schema.org)** 📊
    *   Busca por JSON-LD relevantes (`Organization`, `Person`, `FAQPage`, `Article`, `Product`).
    *   Verifica a presença de links de entidade (`sameAs`) para Knowledge Graphs (Wikidata, Google Knowledge Graph).
    *   Valida a "frescura" do conteúdo (`dateModified` < 90 dias).

4.  **E-E-A-T & Credibilidade** 🏅
    *   **Autoridade**: Verifica a existência de biografia do autor e links para perfis profissionais (LinkedIn, ORCID).
    *   **Citações**: Contabiliza links externos como fontes de credibilidade.
    *   **Dados Fatuais**: Analisa a densidade de estatísticas (números e porcentagens) no conteúdo.

## 🛠️ Pré-requisitos

*   Python 3.6+
*   Pip (Gerenciador de pacotes do Python)

## 📦 Instalação

1.  Clone este repositório:
    ```bash
    git clone https://github.com/seu-usuario/geo-audit.git
    cd geo-audit
    ```

2.  Instale as dependências necessárias:
    ```bash
    pip install requests beautifulsoup4
    ```

## 💻 Como Usar

Execute o script apontando para a URL que deseja analisar:

```bash
python geo-audit.py https://exemplo.com.br
```

### Opções

*   `--json`: Retorna a saída em formato JSON puro (útil para integrações ou pipes).

```bash
# Exemplo de saída JSON
python geo-audit.py https://exemplo.com.br --json > relatorio.json
```

## 📊 Entendendo o Relatório

Ao final da execução, a ferramenta exibe:

*   **GEO Score Geral**: Uma nota de 0 a 100 indicando a otimização para IAs.
*   **Detalhamento**: Status de cada um dos 4 módulos auditados.
*   **Recomendações Prioritárias**: Uma lista de ações críticas para melhorar a pontuação e a visibilidade do site.

## 🤝 Como Contribuir

Contribuições são bem-vindas! Sinta-se à vontade para abrir *issues* ou enviar *pull requests* com melhorias no algoritmo de pontuação, novos bots para verificação ou otimizações no código.

## 📄 Licença

Este projeto é distribuído sob a licença [MIT](LICENSE).
