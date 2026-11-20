# Operação

## Inicialização no Windows

1. Conectar o computador e a ESP32 à rede configurada.
2. Executar `win + R  ==>  sevices.msc  ==>  Mosquitto Broker  ==> Reiniciar ou iniciar` para verificar MySQL e Mosquitto.
3. Executar `iniciar_backend.bat` e acompanhar a inicialização da API e da assinatura MQTT.
4. Ligar a estação e acessar `http://localhost:8000/`.

Os atalhos pressupõem a instalação e a configuração dos respectivos serviços. A execução manual do backend, a partir da raiz do projeto, é:

```powershell
.\.venv314\Scripts\python.exe -m uvicorn python:app --app-dir backend --env-file backend\.env --host 0.0.0.0 --port 8000
```

| Recurso | Endereço local |
|---|---|
| Dashboard | `https://estacao-b1874.web.app` |

## Acesso público pelo Firebase e Cloudflare

O site continua em https://estacao-metedologica.web.app/. O Cloudflare encaminha as consultas HTTPS para a API do notebook; a ESP32 continua publicando no broker MQTT local. As limitações do Quick Tunnel estão descritas na [documentação oficial](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

1. Conectar o notebook e a ESP32 à rede configurada.
2. Confirmar MySQL e Mosquitto com `win + R  ==>  sevices.msc  ==>  Mosquitto Broker  ==> Reiniciar ou iniciar`.
3. Iniciar `.\venv\Scripts\activate  ==>  uvicorn main:app --host 127.0.0.1 --port 8000`.
4. Executar `cloudflared tunnel --url http://127.0.0.1:8000`.Ele cria ou reutiliza o túnel, Depois pegar o link do cloudflare e colocar no config.js no public, atualiza a configuração pública e executar 'firebase deploy --only hosting' no ficheiro com os arquivos '.firebaserc';'firebase.son' e a pasta public
5. Aguardar a mensagem `SITE PUBLICO` e testar o site pelo celular com dados móveis.

O Firebase CLI deve estar instalado e autenticado previamente com `firebase login`. O iniciador não exibe as credenciais de login. Os domínios do Firebase precisam estar em `CORS_ORIGINS` no arquivo privado do backend.

Manter o notebook conectado, o backend e o terminal Cloudflare abertos, e MySQL e Mosquitto em funcionamento. O endereço temporário da API muda ao criar um novo túnel: executar novamente o iniciador faz a republicação, mantendo o endereço do site Firebase. Outra execução enquanto o iniciador estiver ativo não cria um túnel duplicado.

Se o endereço `trycloudflare.com` não resolver, conferir o DNS da rede antes de publicar. O iniciador não altera o DNS do Windows. No notebook da apresentação, o ajuste de DNS deve ser autorizado pelo responsável; guardar a configuração anterior para restauração.

O Quick Tunnel é temporário e não possui garantia de disponibilidade. Fechar o notebook ou perder a conexão interrompe as atualizações públicas. Ele não transforma a instalação local em hospedagem permanente. O ngrok permanece como alternativa antiga e não é utilizado pelo fluxo atual.

## Recursos da interface

- Indicadores de temperatura, umidade, pressão, luminosidade e estimativa do MQ-135.
- Histórico, estatísticas e gráficos das leituras armazenadas.
- Exportação CSV e tabela paginada.
- Cadastro da estação no mapa, busca por CEP e cálculo de distância e vetor local.
- Comparação regional com dados externos de referência.
- Avisos associados à telemetria e demonstrações identificadas na interface.

As ações de limpar e restaurar a exibição alteram a visualização do histórico no navegador; os registros do MySQL são preservados. A edição da localização exige a chave administrativa da instalação.

Os campos do MQ-135 distinguem ADC bruto e PPM estimado. Durante os três minutos iniciais, o dashboard apresenta a indicação de aquecimento. Dados demonstrativos não são inseridos no banco como medições da estação.
