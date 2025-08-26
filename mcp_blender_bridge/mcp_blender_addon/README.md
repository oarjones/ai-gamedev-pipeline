# MCP Blender Add-on

Este add-on proporciona una interfaz para que AI GameDev Pipeline interactúe con Blender.

## Dependencias

Este add-on requiere la librería `websockets` de Python para funcionar. 

## Instrucciones de Instalación de Dependencias para Blender 2.79

Blender 2.79 viene con su propio intérprete de Python. Para instalar `websockets`, sigue estos pasos:

1.  **Encuentra el ejecutable de Python de Blender.** La ubicación puede variar, pero generalmente se encuentra en una ruta similar a esta (en Windows):

    ```
    C:\Program Files\Blender Foundation\Blender\2.79\python\bin\python.exe
    ```

2.  **Abre una terminal o símbolo del sistema.**

3.  **Navega hasta el directorio `bin` de Python de Blender.** Usando el ejemplo anterior:

    ```sh
    cd "C:\Program Files\Blender Foundation\Blender\2.79\python\bin"
    ```

4.  **Instala `websockets` usando pip.** Ejecuta el siguiente comando:

    ```sh
    .\python.exe -m pip install websockets
    ```

    Si el comando anterior no funciona, es posible que necesites actualizar pip primero:

    ```sh
    .\python.exe -m pip install --upgrade pip
    ```

    Y luego intenta instalar `websockets` de nuevo.

Una vez que la instalación se haya completado, el add-on debería funcionar correctamente la próxima vez que habilites el add-on en Blender.
