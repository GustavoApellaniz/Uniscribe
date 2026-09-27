# Preparação para Google Play

O projeto ainda não automatiza publicação. Antes de enviar um bundle:

1. configure a versão e um keystore fora do repositório;
2. preencha Data safety com dados reais (áudio de microfone, transcrição e
   compartilhamento com o backend, se habilitado);
3. publique a política de privacidade em URL HTTPS acessível e mantenha o texto
   em `docs/privacy/privacy-policy.md` sincronizado;
4. exiba a divulgação de consentimento antes de `RECORD_AUDIO` e teste negação;
5. teste HTTPS, timeout, offline, exclusão de áudio temporário e ausência de
   `GEMINI_API_KEY` no APK;
6. revise assinatura, ícones, screenshots, versão mínima e política de
   retenção;
7. execute `./gradlew lint`, `./gradlew test` e `./gradlew bundleRelease` em CI
   com JDK 17.

O arquivo `.github/workflows/play-release.yml` é um placeholder deliberado:
publicação automatizada exige credenciais, assinatura e uma conta de
desenvolvedor configuradas pelo operador.
