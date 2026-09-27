# Política de privacidade — rascunho de produto

**Status:** documento de trabalho; revise com assessoria jurídica antes de
publicar na Google Play.

O UniScribe pode gravar uma aula quando o usuário inicia explicitamente a
gravação. Antes de gravar, o aplicativo deve informar que a captura depende de
permissão do sistema e que o usuário precisa ter autorização dos participantes.

## Dados tratados

- áudio da aula, quando o usuário inicia e interrompe a gravação;
- transcrição bruta e texto filtrado;
- resumo, notas e arquivo `.txt` exportado pelo usuário;
- dados técnicos mínimos necessários para operar e proteger o serviço.

## Finalidades

Os dados são usados para transcrever, filtrar ruído obvio, gerar um resumo
fiel e permitir que o usuário copie ou exporte o resultado.

## Processamento remoto

Quando uma implantação habilita um provedor de ASR ou Gemini, os dados
necessários podem ser enviados ao servidor configurado pelo operador. A API
key do Gemini fica no backend e não no aplicativo. A versão publicada deve
informar o fornecedor, a finalidade, a base legal aplicável e a forma de
exclusão antes de ativar esse fluxo.

## Retenção e exclusão

O MVP de desenvolvimento usa memória e arquivos temporários. A versão de
produção deve declarar por quanto tempo áudio, transcrições e resumos são
mantidos, oferecer exclusão pelo usuário e eliminar dados derivados quando o
prazo de retenção terminar. O código deve ser configurado para não registrar
corpos de API, prompts ou transcrições completas.

## Permissões e segurança

O app solicita `RECORD_AUDIO` para capturar áudio e `INTERNET` apenas quando
uma função remota é usada. Chaves, senhas e arquivos de assinatura não devem
ser incluídos no repositório ou no APK. Use HTTPS, autenticação, rotação de
segredos e criptografia em repouso no servidor.

## Direitos e contato

O documento final deve indicar o controlador/operador, canal de contato,
método de acesso/correção/exclusão e qualquer requisito regional aplicável.
Não publique esta versão sem revisão jurídica.
