1. Colocar la carpeta local_addons que permitirá instalar librerias en el contenedor de HA OS
/config/local_addons/scipy_statsmodels_installer/
├── config.json
├── Dockerfile
└── run.sh

2. Reiniciar el Sistema para Cargar el Add-on Local
Dado que Home Assistant no necesita que agregues un repositorio externo para los add-ons locales, simplemente tienes que reiniciar el Supervisor o reiniciar Home Assistant para que reconozca el add-on.

Ve a Supervisor > System.
En la sección Host, selecciona Reboot Host para reiniciar completamente Home Assistant OS.
Al reiniciar el sistema, Home Assistant buscará en la carpeta local_addons dentro de /config y debería listar el add-on en la sección Add-ons locales en el Supervisor > Add-on Store.

3. Instalar el Add-on
Ajustes --> Complementos --> Tienda de complementos
