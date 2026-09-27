# UniScribe

MVP Android para gravar uma aula, transcrever, remover ruído lexical, gerar um
resumo fiel e exportar `.txt`.

> **Estado:** fluxo headless e clientes implementados; o ASR real, o backend de
> produção e a publicação na Play Store ainda exigem configuração, credenciais,
> testes em dispositivo e revisão jurídica.

## Fluxo

```text
Microfone -> arquivo/chunks -> transcrição ASR -> filtro conservador
          -> resumo local/Gemini -> API/cliente -> Copy/Export .txt
```

A chave do Gemini pertence exclusivamente ao processo Python servidor. O APK
não deve conter `GEMINI_API_KEY`.

## Início rápido do backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
# O servidor lê o ambiente do processo; para usar .env local:
set -a; . ./.env; set +a
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest -q
PYTHONPATH=. python main.py --backend
```

O servidor escuta em `127.0.0.1:8080` por padrão. Endereços e provedores reais
são injetados em `LectureBackend`; o stub local não finge decodificar áudio. O
cliente web local usa CORS restrito a `localhost:3000`/`127.0.0.1:3000`.
Consulte `docs/backend.md` para os contratos JSON/multipart e para a pesquisa
oficial datada.

## Cliente Kivy

```bash
pip install -r requirements.txt
PYTHONPATH=. python main.py
```

O cliente Kivy é útil para desktop e protótipo. A captura real do microfone em
um dispositivo deve ser fornecida por um adaptador de plataforma; o
`AudioRecorder` Python sozinho apenas gerencia o caminho temporário.

## Android nativo

O módulo `:app` usa Views nativas, `MediaRecorder` e `HttpURLConnection`:

```bash
./gradlew assembleDebug \
  -PUNISCRIBE_TRANSCRIPTION_URL=https://api.example.test/v1/process-audio
```

Para desenvolvimento local no emulador, use `http://10.0.2.2:8080/v1/process-audio`
e a configuração de rede debug. Para backend não local, use HTTPS e injete no
app um token de usuário/sessão de curta duração; `UNISCRIBE_AUTH_TOKEN` é
apenas configuração do servidor. Nunca coloque a chave Gemini no build do app.
Veja `docs/android.md`.

## Testes e qualidade

- `tests/` cobre domínio, filtro, transcrição injetada, resumo, persistência,
  exportação, Gemini com transporte falso e API HTTP.
- Nenhum teste usa microfone, modelo pesado, rede real ou segredo.
- `.github/workflows/python-ci.yml` executa a suíte Python.
- Documentos de privacidade e termos são rascunhos e precisam de revisão legal.

## Estrutura principal

```text
uniscribe/
  domain/       modelos e casos de uso
  data/         repositórios
  services/     áudio, ASR, filtro, resumo, Gemini e exportação
  backend.py    API HTTP local
  screens/      UI Kivy
app/            cliente Android nativo
frontend/       cliente web estático (opcional)
core/, data/, domain/, feature/  módulos Android legados não incluídos no
                                build mínimo :app
```

Consulte também `docs/backend.md`, `docs/android.md`,
`docs/play-release.md` e `docs/privacy/privacy-policy.md`.
