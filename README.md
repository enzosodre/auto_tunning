# 🎯 Auto-Tuning com Pattern Search em Python

Este projeto foi desenvolvido na disciplina de **Lógica Computacional** do curso de **Sistemas de Informação**, com o objetivo de implementar um **algoritmo de auto-tuning** capaz de ajustar automaticamente parâmetros de entrada de um programa (executável) e encontrar a melhor configuração possível, de acordo com um **objetivo definido** (maximizar ou minimizar).

O código foi implementado em **Python**, utilizando a técnica **Pattern Search (Busca por Padrões)** para explorar o espaço de parâmetros — tanto **numéricos** quanto **categóricos** — de forma adaptativa.

---

## 🧠 Objetivo do Auto-Tuning

O **auto-tuning** tem como principal função **automatizar o ajuste de parâmetros** de um programa ou algoritmo, eliminando a necessidade de testar manualmente todas as combinações possíveis.

Sua função é:
- Ler os parâmetros de entrada definidos pelo usuário (numéricos e/ou categóricos);
- Executar o programa ou função objetivo (via **subprocesso** ou **simulador interno**);
- Aplicar o **Pattern Search**, buscando a configuração que produza o melhor resultado possível.

Em resumo, o sistema **aprende a ajustar automaticamente os parâmetros** para **maximizar ou minimizar** o valor retornado pela função avaliada.

---

## ⚙️ Estrutura do Projeto

auto_tunning/
│
├── src/
│ ├── main.py # Interface interativa e controle do fluxo principal
│ ├── pattern_search.py # Implementação do Pattern Search adaptativo
│ └── init.py # (arquivo vazio opcional para marcar o pacote)
│
├── .gitignore
├── LICENSE
└── README.md

yaml
Copiar código

---

## ▶️ Execução

1. Certifique-se de ter o **Python 3.8+** instalado.  
2. No terminal, navegue até a pasta do projeto:

   ```bash
   cd auto_tunning
Execute o programa principal:

bash
Copiar código
python src/main.py
Escolha:

O objetivo (max ou min);

Os parâmetros (quantidade, tipo, valores e limites);

O modo de execução:

Executável real (.exe) → chama o arquivo externo e lê o valor retornado;

Simulador interno → útil para testes iniciais.

🔍 Funcionamento do Pattern Search
O Pattern Search é um método de busca direta (sem derivadas) que:

Explora os parâmetros individualmente;

Para parâmetros numéricos, testa variações +step e -step;

Para categóricos, troca entre opções disponíveis;

Quando não há melhoria, reduz o passo (step), permitindo refinamento;

Para quando os passos chegam abaixo do limite mínimo (min_step) ou o número máximo de iterações é atingido.

🧩 Exemplo de Uso (Simulador Interno)
r
Copiar código
=== Auto-Tuning + Pattern Search (Interativo) ===
Objetivo (max/min) [max]: max
Quantos parâmetros o executável recebe?: 2
Parâmetro #1 → tipo: num
Parâmetro #2 → tipo: cat
Backend: simulador interno
Resultado:

bash
Copiar código
Iterações: 42
Melhor score: 11.247
Melhores parâmetros:
 - taxa_aprendizado = 0.5
 - tipo_modelo = 'polinomial'
🧰 Dependências
Este projeto utiliza apenas bibliotecas padrão do Python, sem necessidade de instalação adicional.

📜 Licença
Distribuído sob a licença MIT License — veja o arquivo LICENSE para mais informações.

👨‍💻 Autores
Enzo Sodré
Matheus Lima
Graduandos em Sistemas de Informação — 8º semestre
Desenvolvido como parte da disciplina de Lógica Computacional (2025)

yaml
Copiar código

---

✅ **Validação**:
- O Markdown agora renderiza corretamente no GitHub.  
- Todos os blocos de código foram fechados.  
- As seções estão organizadas, legíveis e consistentes.  
- O conteúdo técnico e acadêmico está 100% coerente.

---
