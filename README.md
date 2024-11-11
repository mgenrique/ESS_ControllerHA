# Estado de la rama congelada_v2
Esta rama se ha creado al finalizar el desarrollo del custom Component ESS Controller en la versión que trabaja con el Addon Prophet InfluxDB Addon. Se van a incorporar nuevas funcionalidades como input numbers en la UI que den alguna libertad de acción al usuario en el día a día, sin depender de parametros tan estáticos como los solicitados en el flujo de configuración.

# ESS_ControllerHA
![ess_controller](_images/icon.png)

The **ESS controller** is a target soc calculator for **Home Assistant**. It is a custom component that uses data from different sources to perform hourly scheduling of the system's battery SoC, so that the cost of purchasing energy from the grid is minimal. To do this, it obtains historical data from **InfluxDB** about the home consumption, actual solar production and the historical predictions obtained from **Forecast.Solar**.
Using the **Prophet** library, it generates demand forecasts for the next few hours.
The electricity purchase and sale prices are obtained from the official **ESIOS** component (Spain electricity hourly price PVPC), so for the moment, the component is only useful for the Spanish territory.
The solar production forecasts are obtained from Forecast.Solar and will be weighted by hours with the success coefficients obtained from the analysis of historical data, before sending them to the target calculator.
The configuration flow asks the user for the parameters necessary to characterize the installation (battery data, location, and system power and efficiency).
The development has been done on a system with a **Victron Energy** Multiplus inverter but it is adaptable to any inverter model that is capable of providing information in the form of Home Assistant sensors.

With all the above information, the software coordinates all the information sources to pose a linear programming problem that is solved using **PuLP**.

The final result is a SoC schedule that the system must try to follow.

With this information, the Modbus connection with the inverter is used to maintain the grid set point that allows the calculated SoC to be reached.

## Important information for installation
The first version of this component has been developed in Ubuntu on a Home Assistant Core installation running in a Python 3.12 virtual environment.
In Ubuntu the Prophet library is not a problem since it is possible to install it. However in Home Assistant OS, it is not possible to have this library since the OS is a minimal system based on Alpine.
In order for the component to be more general-purpose, Prophet has had to be abandoned and the `statsmodels` library is used instead. This library is not part of HA OS, so it is necessary to install it before being able to use the custom component.
In manifest.json the requirement for `statsmodels` is omitted so that the system does not try to install it, so only the line remains:
```json
"requirements": ["pulp"]
```
However, for an installation on a different operating system, the following should be included:
```json
"requirements": ["pulp", "statsmodels"]
```
or in the case of wanting to use Prophet (only if not HA OS)
```json
"requirements": ["pulp", "prophet"]
```

If you don't have `statsmodels` yet in Home Assistant OS, you can get it by installing the Addon from the repository
https://github.com/mgenrique/HassOS_scipy_statsmodels_installer

To do this, in the HA UI, go to `Settings` --> `Addons` --> `Addon Store`.

In the button with the 3 dots, select `Repositories` and add it.

This will make the addon appear in the UI under `HassOS_scipy_statsmodels_installer` and you can install it.

This Addon will only run once and its only mission is to install the `statsmodels` library from the Alpine packages at:
https://pkgs.alpinelinux.org/package/edge/community/x86/py3-statsmodels


## TODO:
The component is still in very early development stage. Use at your own risk.

In the future, solutions will be explored to make `FB Prophet` the tool in charge of making estimates for all types of installations. For the moment, users who install it on HA Os will at least get reasonable estimates using `statsmodels`.

A possible source of inspiration for this task can be found at:
- https://github.com/scirag/fbprophet-docker/tree/master
- https://hub.docker.com/r/safakcirag/fbprophet
