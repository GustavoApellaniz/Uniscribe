# UniScribe — interface do MVP

O repositório tem três clientes: web estático (`frontend/`), Kivy
(desktop/Buildozer) e Android nativo (`app/`). Todos expõem o mesmo fluxo
mínimo:

```text
Start Listening -> gravando -> Stop -> Processing... -> resumo -> Copy / Export .txt
```

## Referência de UX

O fluxo toma apenas padrões de usabilidade de ferramentas como Otter.ai e
Notta:
início/parada em um toque, estado visível, texto e resumo separados, e ações
de copiar/exportar. Nenhuma tela, marca ou implementação desses produtos foi
copiada.

## Web estático

`frontend/index.html`, `frontend/styles.css` e `frontend/app.js` implementam o
mesmo fluxo no navegador. O botão de demonstração é explícito; quando o modo
offline está desativado, uma falha do backend não é substituída por fixture.
Conteúdo vindo do transcript/summary é renderizado como texto, nunca como HTML.

Sirva a pasta por HTTP (não abra `file://`) para habilitar permissões de
microfone:

```bash
python -m http.server 3000 --directory frontend
```

## Kivy

`uniscribe/screens/home.py` implementa os estados `idle`, `listening`,
`processing`, `ready` e `error`. Recorder, transcriber, summariser,
permission checker, network checker, clipboard e diretório de exportação são
injetáveis. Isso permite testar a interface com dublês sem microfone, display
Kivy ou rede.

O `AudioRecorder` Python é um espaço reservado para o contrato de arquivo. Em um
build Kivy Android, injete um adaptador que capture amostras reais; o cliente
Android nativo já usa `MediaRecorder` e grava `.m4a` no cache do app.

## Android nativo

O módulo `:app` usa Views nativas para evitar uma dependência de UI. Ele:

1. mostra uma divulgação antes de solicitar `RECORD_AUDIO`;
2. grava em cache com `MediaRecorder` (AAC/M4A, 44,1 kHz, mono);
3. faz upload multipart para o endpoint Python configurado no build;
4. mostra o processamento, o resumo e as ações de copiar/exportar via Storage
   Access Framework;
5. cancela a captura ao sair da atividade e não continua gravando em segundo
   plano.

O cliente não contém `GEMINI_API_KEY`. A configuração de endpoint, HTTPS e
limitações está em `docs/android.md`.

## Estados e falhas

- Permissão negada: a tela continua utilizável e orienta como conceder a
  permissão depois.
- Internet indisponível: o backend pode falhar explicitamente; o cliente Kivy
  pode usar fallback local, enquanto o app Android mostra erro e preserva a
  gravação apenas durante a requisição.
- Resposta vazia: o cliente não transforma um resultado vazio em sucesso.
- Exportação: UTF-8 em arquivo `.txt`; o Android usa o seletor de documentos do
  sistema.

## Testes

O fluxo Kivy é testado por compilação e smoke tests com dublês. O build Android
deve ser executado em uma máquina com JDK, SDK e emulador/dispositivo:

```bash
./gradlew test
./gradlew lint
./gradlew assembleDebug
```
