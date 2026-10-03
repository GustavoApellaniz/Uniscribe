# UniScribe — backend Python

Este documento descreve a fatia implementada do MVP. O código não tenta
simular Whisper ou Gemini: provedores reais são injetados no servidor e os
testes usam fakes determinísticos.

## 1. Resumo da solução

```text
[Microfone Android] -> [áudio/chunks] -> [backend Python]
                                           |
                                           +-> [transcrição ASR]
                                           +-> [filtro conservador]
                                           +-> [resumo local ou Gemini]
                                           +-> [persistência temporária]
                                           +-> [JSON para o app]
```

O app Android nativo é o cliente. O processo Python é o limite que pode conter
`GEMINI_API_KEY`; a chave nunca deve ser colocada no APK, no código do cliente
ou em uma resposta da API.

## 2. Componentes e responsabilidades

| Módulo | Responsabilidade |
| --- | --- |
| `uniscribe/domain/models.py` | Entidades e resumo estruturado, sem dependências de framework. |
| `uniscribe/services/audio.py` | Ciclo de vida de arquivo temporário, validação e chunks ordenados. |
| `uniscribe/services/transcription.py` | Protocolo de ASR e stub local; não inventa endpoint Whisper. |
| `uniscribe/services/whisper_local.py` | Adaptador opcional para o pacote local Whisper, carregado sob demanda. |
| `uniscribe/services/filtering.py` | Remove apenas ruído óbvio e conserva conteúdo acadêmico. |
| `uniscribe/services/summarization.py` | Fallback offline extrativo e determinístico. |
| `uniscribe/services/gemini.py` | Cliente server-side opcional, JSON validado e transporte injetável. |
| `uniscribe/domain/usecases.py` | Pipeline `transcrever -> filtrar -> resumir`. |
| `uniscribe/data/repositories.py` | Store em memória para o MVP e testes. |
| `uniscribe/backend.py` | API HTTP local, limitada e sem chave no cliente. |
| `uniscribe/services/export.py` | Exportação UTF-8 `.txt`. |

## 3. Decisões de arquitetura

| Problema | Opções | Comparação | Decisão | Justificativa |
| --- | --- | --- | --- | --- |
| Captura | `MediaRecorder`, `AudioRecord` | `MediaRecorder` é simples; `AudioRecord` dá mais controle, com mais código | Android `MediaRecorder` + limite Python | Menos código no MVP e captura real no cliente. |
| ASR | Whisper local, ASR remoto, stub | Local preserva privacidade, mas exige modelo/CPU; remoto é mais simples, mas envia áudio; stub é determinístico | Adaptador injetado; stub por padrão | Testa o fluxo sem custo e permite escolher provedor real sem mudar a API. |
| Gemini | API no app, API no backend, fallback local | App expõe segredo e é difícil de proteger; backend centraliza chave; fallback não depende de rede | Backend com `GEMINI_API_KEY` no ambiente | Reduz exposição de credenciais e permite fallback auditável. |
| Persistência | Banco, arquivo, memória | Banco é durável e caro; arquivo exige criptografia; memória é simples e volátil | `MemoryStore` no MVP | Mantém o marco headless barato; adaptador durável é fase posterior. |
| Exportação | PDF, HTML, `.txt` | PDF/HTML são mais complexos; `.txt` é portátil e auditável | UTF-8 `.txt` | Atende o fluxo mínimo com baixa complexidade. |

### Captura de áudio

**Problema:** o MVP precisa gravar sem transformar a UI em um gravador
complexo.

**Opções:** `AudioRecord`/`MediaRecorder` no Android ou um serviço remoto.

**Decisão:** o cliente Android captura o microfone e envia arquivo/chunks ao
backend. `AudioRecorder` Python gerencia somente o contrato de caminho,
estado e validação. O backend não recebe uma chave de IA.

**Justificativa:** a permissão `RECORD_AUDIO` e a operação de microfone ficam
no cliente; o backend pode ser testado sem hardware.

### Transcrição

`TranscriptionAdapter` aceita uma função chamável ou objeto com
`transcribe(audio, language)`. O stub local só devolve fixtures conhecidas e
retorna texto vazio quando não há fixture. Um adaptador Whisper local,
Whisper em processo ou serviço de ASR deve ser registrado pela implantação;
o código não presume endpoint, preço ou formato de resposta.

### Filtro

O filtro é conservador. Fillers isolados, repetições consecutivas e marcadores
de silêncio podem sair; frases com definições, exemplos, perguntas, datas,
números, fórmulas e marcadores de incerteza são protegidas. O texto bruto é
sempre mantido em `Transcript.text`; `filtered_text` é uma cópia derivada.

### Gemini

`GeminiClient` é opcional. O servidor injeta transporte HTTP e obtém a chave de
`GEMINI_API_KEY` no momento da chamada. A resposta precisa ser um envelope
Gemini com JSON válido; texto livre é rejeitado em vez de ser interpretado por
tentativa. A implementação usa por padrão a API atual de Interactions
(`/v1beta/interactions`) e permite `api_style="generate_content"` somente para
um endpoint legado explicitamente configurado. Use um modelo disponível na
conta e valide a versão do endpoint na implantação.

### Pesquisa verificada em 24/09/2026

Os itens a seguir são fatos das páginas oficiais consultadas; preços e
disponibilidade continuam sujeitos a mudança:

- A documentação atual do Gemini lista `gemini-3.8-flash` e o endpoint REST de
  Interactions. A página de transcrição lista `gemini-3.5-transcribe`, com
  detecção automática de idioma, diarização e timestamps opcionais. O modo
  `smart` remove fillers; o modo verbatim preserva a fala. Para arquivos
  longos, a documentação recomenda o Files API.
- A página de preços do Gemini informa, para `gemini-3.8-flash` Standard
  durante 2026: US$ 0,75/1M tokens de entrada e US$ 3,75/1M de saída até
  31/12/2026 (mudam em 01/01/2027). Para `gemini-3.5-transcribe`, a mesma
  página mostra cerca de US$ 0,003/minuto de entrada de áudio e
  US$ 0,002/minuto de saída de texto. A camada gratuita tem limites e um
  tratamento de dados diferente do plano pago; não trate a camada gratuita
  como produção.
- A documentação do Whisper descreve modelos multilíngues, exige `ffmpeg` para
  arquivos comprimidos e processa o áudio em janelas deslizantes de 30
  segundos. O modelo e o pacote são uma opção local; o servidor pode injetar
  esse adaptador sem colocar o modelo no APK.
- Android exige permissões perigosas em runtime a partir do API 23. A
  orientação oficial é pedir a permissão no contexto da ação, explicar o motivo
  e degradar a função se o usuário negar. A documentação de mídia usa
  `MediaRecorder`/`AudioRecord`; o código Android escolhe `MediaRecorder` para o
  MVP.
- A política de User Data do Google Play classifica microfone como dado
  sensível. Quando a coleta não for obviamente esperada, o app deve exibir
  divulgação destacada no app e obter consentimento afirmativo antes da
  permissão, usar HTTPS, publicar política de privacidade e preencher Data
  safety de forma consistente. Se houver conta, exclusão de conta e dados
  precisa estar disponível no app e externamente.

### Persistência e retenção

O MVP usa `MemoryStore`; isso evita um banco e um custo recorrente no
protótipo. Uma implantação durável deve criptografar em repouso, limitar
retenção, registrar consentimento e excluir áudio/transcriptos conforme a
política escolhida. O handler HTTP remove arquivos temporários após o
processamento, salvo `keep_audio=True` explícito para desenvolvimento.

## 4. Contrato HTTP local

O servidor é iniciado com:

```bash
set -a; . ./.env; set +a
PYTHONPATH=. python -m uniscribe.backend
```

O processo não faz parsing automático de `.env`; use um gerencior de segredos
ou exporte as variáveis explicitamente.

Por padrão, `UNISCRIBE_TRANSCRIBER=stub` é um stub determinístico. Uma
implantação local pode usar `UNISCRIBE_TRANSCRIBER=whisper-local` depois de
instalar `openai-whisper` e `ffmpeg`; o pacote/modelo não é baixado
automaticamente.

Endpoints próprios do UniScribe (não são endpoints oficiais de Whisper ou
Gemini):

### `GET /health`

```json
{"status":"ok","service":"uniscribe"}
```

### `POST /v1/process-audio`

O cliente pode enviar `multipart/form-data` com o campo `audio` e os campos
`lecture_id`, `course_id`, `title` e `language_tag`; esse é o formato usado
pelo cliente Android nativo. Para integrações simples, também é aceito JSON
com `audio_base64`. O limite padrão é 25 MiB.

```json
{
  "lecture_id": "lecture-123",
  "course_id": "course-1",
  "title": "Aula 1",
  "language_tag": "pt-BR",
  "audio_base64": "[AUDIO_CHUNK_OR_FILE]"
}
```

Resposta (os campos podem variar conforme o provedor de ASR injetado):

```json
{
  "lecture": {"id":"lecture-123","title":"Aula 1","status":"recorded"},
  "transcript": {
    "id":"transcript-1",
    "raw_text":"[RAW_TRANSCRIPT]",
    "filtered_text":"[FILTERED_TRANSCRIPT]",
    "language_tag":"pt-BR"
  },
  "summary": {
    "title":"Aula 1",
    "bullets":["[SUMMARY]"],
    "uncertainties":[],
    "source_transcript_id":"transcript-1"
  },
  "data": {"transcript":"[FILTERED_TRANSCRIPT]","summary":"[SUMMARY]"}
}
```

### `POST /v1/process-chunks`

Aceita chunks ordenados para clientes que já fazem captura incremental. Cada
item deve ter `sequence` começando em zero e `audio_base64`; o backend rejeita
gaps, duplicatas e payload vazio antes de chamar o ASR.

```json
{
  "lecture_id": "lecture-123",
  "mime_type": "audio/wav",
  "chunks": [
    {"sequence": 0, "audio_base64": "[AUDIO_CHUNK_0]"},
    {"sequence": 1, "audio_base64": "[AUDIO_CHUNK_1]"}
  ]
}
```

### `POST /v1/process-transcript`

Permite retry/importação quando o ASR já foi executado:

```json
{"lecture_id":"lecture-123","transcript":"[RAW_TRANSCRIPT]"}
```

O filtro e o resumo usam o mesmo pipeline do upload.

Para o cliente web local, o backend permite CORS de `http://localhost:3000` e
`http://127.0.0.1:3000` por padrão. Em produção, configure explicitamente as
origens permitidas e não use `*` com credenciais. Para escutar fora de
`localhost`, configure `UNISCRIBE_AUTH_TOKEN`; nesse caso as requisições
precisam de `Authorization: Bearer <token>`. O Gemini continua sendo acessado
somente pelo processo servidor.

### Exemplo de requisição ao Gemini (servidor)

Com o endpoint atual de Interactions, o cliente HTTP do servidor envia uma
requisição equivalente a:

```json
{
  "model": "gemini-3.8-flash",
  "input": "[FILTERED_TRANSCRIPT]",
  "system_instruction": "Resuma somente com base na transcrição; marque incertezas.",
  "response_format": {"type": "text", "mime_type": "application/json"},
  "store": false
}
```

A resposta de texto precisa conter JSON válido, por exemplo:

```json
{
  "title": "[TÍTULO]",
  "summary": "[RESUMO]",
  "key_points": ["[CONCEITO]"],
  "definitions": ["[DEFINIÇÃO]"],
  "examples": ["[EXEMPLO]"],
  "formulas": ["[FÓRMULA]"],
  "important_points": ["[PONTO]"],
  "questions": ["[DÚVIDA]"],
  "uncertainties": ["[INCERTEZA]"]
}
```

Isso é um exemplo de payload, não uma promessa de que todos os campos serão
retornados. `GeminiClient` valida o envelope e `GenerateLectureSummary` mapeia
os campos para o modelo de domínio.

### Placeholders de contrato

- `[AUDIO_CHUNK]`: bytes ou Base64 de um chunk com `sequence` e MIME type.
- `[RAW_TRANSCRIPT]`: texto integral retornado pelo ASR.
- `[FILTERED_TRANSCRIPT]`: texto derivado, conservativeamente filtrado.
- `[GEMINI_REQUEST]`: payload server-side com `model`, `input`,
  `response_format` e `store: false`.
- `[SUMMARY]`: objeto JSON validado com título, conceitos, definições,
  exemplos, fórmulas, pontos, dúvidas, resumo final e incertezas.

## 5. Exemplo de sessão

```text
Input: [30 minutos de áudio]
Whisper/ASR: [RAW_TRANSCRIPT]
Filtro: [FILTERED_TRANSCRIPT]
Gemini ou fallback: [SUMMARY]
Usuário: copia o resumo e exporta lecture_summary.txt
```

O resumo só deve afirmar fatos presentes no texto filtrado. Se o ASR ou o
modelo estiverem indisponíveis, a API retorna erro ou o fallback local é
identificado; ela não fabrica uma transcrição.

## 6. Segurança e privacidade

- O APK não recebe `GEMINI_API_KEY`.
- HTTPS, autenticação, rotação de segredos, criptografia do banco e política de
  retenção são decisões de implantação, não algo que o stub local finja resolver.
- O servidor local limita o tamanho do body, o tempo de leitura e o número de
  handlers concorrentes. Em produção, ainda use um reverse proxy com TLS,
  rate limit e limites de conexão.
- Não registre áudio, transcrições completas, prompts ou corpos de resposta em
  logs de produção.
- Obtenha consentimento dos participantes e trate dados de Manifestação de
  acordo com a legislação aplicável. Valide os requisitos com assessoria jurídica.
- Solicite apenas permissões necessárias. No Android, `RECORD_AUDIO` e
  `INTERNET` devem ser explicadas na tela; armazenamento externo amplo deve ser
  evitado.
- Uma chamada externa ao Gemini é um processamento de dados. A política de
  privacidade deve informar esse fluxo e permitir exclusão.

## 7. Custos

Não há preço fixo embutido no projeto. Para comparar opções, calcule:

```text
custo_por_aula =
  minutos_da_aula / 60 * preço_ASR_por_minuto
  + tokens_enviados / 1_000_000 * preço_entrada_por_1M
  + tokens_saída / 1_000_000 * preço_saída_por_1M
  + armazenamento_gb_mês * preço_armazenamento_gb_mês
  + custo_fixo_do_backend
```

Os preços de ASR, Gemini, armazenamento e backend variam por região, modelo,
volume, data e contrato. Para uma aula de 60 minutos, usando a estimativa
publicada para `gemini-3.5-transcribe` em 24/09/2026, apenas o texto de
transcrição seria aproximadamente `60 × (0,003 + 0,002) = US$ 0,30` no pricing
Standard; isso não inclui armazenamento, backend, resumo ou impostos.
Para um resumo textual, substitua os minutos por tokens de entrada/saída e
consulte a tabela do modelo escolhido. Não reutilize esse valor depois de
31/12/2026 sem nova consulta. O fallback local permite validar o fluxo sem
custo de API, mas não substitui uma avaliação de qualidade do Whisper escolhido.

## 8. Plano de implementação

1. **MVP básico:** implementar a captura no cliente, validar arquivo e executar
   ASR injetado; testar com fixture, sem microfone.
2. **Filtragem:** ativar `filtering.py`, preservar raw/filtered e revisar falsos
   positivos com amostras reais.
3. **Resumo:** usar fallback local; ativar Gemini somente no servidor após
   validar prompt, JSON, timeout e orçamento.
4. **Exibição/exportação:** mostrar estados de gravação/processamento, copiar e
   exportar `.txt`; não bloquear a gravação por indisponibilidade de rede.
5. **Play Store:** testes de permissão, política de privacidade, retenção,
   conta de demonstração quando aplicável, revisão de conteúdo e build
   assinado.

## 9. Referências para validação da implantação

- Android Developers — permissões em runtime e explicativas:
  https://developer.android.com/training/permissions/requesting
- Android Developers — `MediaRecorder`:
  https://developer.android.com/reference/android/media/MediaRecorder
- Gemini API — texto/Interactions:
  https://ai.google.dev/gemini-api/docs/text-generation
- Gemini API — transcrição:
  https://ai.google.dev/gemini-api/docs/transcribe
- Gemini API — preços:
  https://ai.google.dev/gemini-api/docs/pricing
- OpenAI Whisper (repositório/documentação):
  https://github.com/openai/whisper
- Google Play — User Data e consentimento:
  https://support.google.com/googleplay/android-developer/answer/10144311

Links não substituem a verificação da versão vigente. O código não deve afirmar
que um modelo, preço ou endpoint continue disponível sem uma checagem atual.

## 10. Testes

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest -q
```

Os testes devem usar fakes para ASR e transporte HTTP. Não coloque chaves
reais em testes, fixtures, logs ou commits.
