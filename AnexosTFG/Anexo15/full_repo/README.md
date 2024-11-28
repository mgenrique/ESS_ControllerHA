This repository is structured to be used in the Home Assistant Addon Store repository list, and is specifically designed for installing the **Prophet InfluxDB Addon**.

An Addon for Home Assistant that allows forecasting future data using the Prophet library and can use InfluxDB data for model training.

To use it, in the HA UI, go to `Settings` --> `Addons` --> `Addon Store`.

In the button with the 3 dots, select `Repositories` and add the url: [https://github.com/mgenrique/hassos_prophet_addon](https://github.com/mgenrique/hassos_prophet_addon)

This will make the addon appear in the UI under HassOS Prophet Addons and you can install it.

- The folder required for installing the addon is `prophet-influx-multi-addon`.

- The `prophet-influx-multi` folder contains information for the process of creating the Docker image that serves as the basis for the addon

- The `test` folder contains sample Python scripts for testing the addon after installation.

This addon has been created as a solution to the installation limitations of the custom component [ESS Controller](https://github.com/mgenrique/ESS_ControllerHA) in Home Assistant OS.

