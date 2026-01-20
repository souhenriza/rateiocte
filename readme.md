Aplicação desktop desenvolvida em Python para automatização de processo interno de rateio de custos de transporte. Realiza leitura de planilhas em Excel, PDFs e XMLs, com geração de PDFs rateados e opções auxiliares. 

O sistema foi projetado com arquitetura modular, separando interfaces gráficas das regras de negócio, utilitários e configurações padrão, o que facilita manutenções.



## Funcionalidades principais:
- Leitura de planilha Excel com dados de rateio

- Processamento automático de PDFs de CT-e

- Leitura e validação de XMLs de CT-e

- Associação CT-e ↔ PDF ↔ XML por chave

- Cálculo proporcional de rateio por operação

- Ajustes automáticos de arredondamento

- Identificação de CT-e do tipo Complemento

- Geração de PDFs rateados

- Opção de gerar PDF único consolidado

- Persistência automática de configurações (JSON)

- Interface gráfica amigável (Tkinter)

- Barra de progresso e log em tempo real


## Arquitetura do projeto

CodFinal RateioCTe/

├── main.py      # Ponto de entrada da aplicação


├── assets/
    ├── adimax.png
    └── adimax.ico

├── config/
     └── config.json      # Configurações persistidas

├── src/
│   ├── __init__.py
│   ├── gui.py              # Interface gráfica (Tkinter)
│   ├── rateio.py           # Regra de negócio principal
│   ├── pdf_utils.py        # Manipulação de PDFs
│   ├── xml_utils.py        # Leitura e validação de XML CT-e
│   ├── utils.py            # Funções auxiliares (conversões, validações)
│   └── config.py           # Persistência de configurações

├── requirements.txt
└── README.md
---

## Para executar o projeto:

Para executar o projeto de forma local, é necessário ter o **Python 3** instalado e acesso a um terminal (VSCode, Pycharm, Terminal do Windows).

Primeiro, faça o download ou clone o repositório para o seu computador. Em seguida, abra o terminal e navegue até a raiz do projeto onde vai encontrar o arquivo **main.py**.

Recomendo a criação de um ambiente virtual para isolar as dependências do projeto. Após criar e ativar o ambiente virtual, instale todas as dependências (requeriments.txt na raiz do projeto).

Com as dependências instaladas, você pode verificar o projeto executando o arquivo **main.py**. Esse arquivo abrirá uma interface gráfica baseada em TkInter que você verá:

- Campo para seleção do arquivo .xlsx
- Campo para seleção da pasta onde se encontra os DACTE (Documento Auxiliar de Conhecimento de Transporte Eletrônico)
- Campo para seleção da pasta onde se encontra os arquivos.xml (Opcional)
- Campo para seleção da pasta onde serão salvos os arquivos.pdf gravados com as informações da planilha.xlsx.

Após selecionar os diretórios e arquivos aperte em **INICIAR PROCESSAMENTO**. O sistema exibirá o progresso por meio de uma barra de progresso em tempo real e registrará no log da interface. 

As configurações das pastas e diretórios são salvos de forma automática para que não seja necessário.







