# Cliente web UniScribe

Sirva esta pasta por HTTP:

```bash
python -m http.server 3000 --directory frontend
```

Abra `http://localhost:3000`. O botão de demonstração usa fixtures locais; para
usar o backend, desative o modo demonstração e configure o endpoint Python nas
Configurações. O cliente nunca envia `GEMINI_API_KEY`.

Não abra `index.html` via `file://`, pois o navegador pode bloquear APIs de
microfone e requisições para outro origen. O cliente web local não envia
autenticação; para uma implantação remota, adicione autenticação de usuário e
CORS explícito. Para produção, sirva por HTTPS e revise a política de
privacidade.
