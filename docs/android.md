# Android nativo — MVP

O cliente Android usa Views nativas e `MediaRecorder`; não há chave Gemini no
APK. O backend recebe o arquivo `.m4a` por `multipart/form-data` e devolve o
resumo.

## Configuração de desenvolvimento

O endpoint é fornecido no build, nunca fica no código-fonte:

```bash
./gradlew assembleDebug \
  -PUNISCRIBE_TRANSCRIPTION_URL=http://10.0.2.2:8080/v1/process-audio
```

O manifesto e a configuração de rede em `src/debug` permitem HTTP somente no
build debug; o build release permanece com `usesCleartextTraffic=false`. Para um
servidor remoto, use HTTPS. O app não recebe token compartilhado por
`-P`; a implementação de produção deve injetar em `AppContainer` um token de
usuário/sessão de curta duração. Nunca use a `GEMINI_API_KEY` como propriedade
do app.

O cliente declara `RECORD_AUDIO` e `INTERNET`, solicita a permissão no contexto
da ação e presenta uma divulgação persistida antes do primeiro uso. A gravação é
cancelada quando a atividade sai, para não iniciar captura em segundo plano.

## Limites do MVP

- A implementação grava uma aula inteira e processa depois de `Stop`; chunks e
  transcrição incremental são fronteiras do backend, mas não são transmitidos
  pelo cliente nativo ainda.
- O backend precisa de um adaptador ASR real injetado. O stub local é honesto e
  não finge transcrever áudio.
- O build nativo exige JDK 17, SDK Android e acesso aos repositórios Gradle. O
  wrapper foi incluído, mas este ambiente não possui Java para executar o build.
- `compileSdk`/`targetSdk` usam 35, uma combinação estável para AGP 8.7.3;
  confirme a política vigente antes de publicar.

## Verificação

```bash
./gradlew test
./gradlew lint
./gradlew assembleDebug
```

O wrapper baixa a distribuição Gradle especificada. Em CI, fixe também o JDK e
as credenciais/serviços necessários em um ambiente secreto.
