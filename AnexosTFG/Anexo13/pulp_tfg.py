# Problema combinado de minimización del coste de la energía comprada y maximización de la energía almacenada en la batería
# Minimización: total_cost - w * final_soc
# w es un peso que refleja la importancia relativa de maximizar el SoC frente a minimizar el coste.
# el peso w se calcula en base el precio medio de la electricidad para valorar la energía almacenada
# Exigir que el SoC en el último periodo se mayor que el SoC inicial
# Establecer un soc mínimo del que no está permitido bajar
# Contemplar las eficiencias de carga y descarga de la batería
# Contemplar la posibilidad de vender energía a la red
# Contemplar la potencia maxima contratada con la compañía eléctrica que limita la maxima energía que se puede comprar por ciclo

import pulp
import pandas as pd
from datetime import datetime, timedelta

# Parámetros de entrada
battery_capacity = 2560                # Capacidad máxima de la batería (Wh)
max_charge_energy_per_period = 1200     # (Wh), debido a la máxima potencia de carga max_charge_power(W)
max_discharge_energy_per_period = 1200  # (Wh), debido a la máxima potencia de descarga max_discharge_power(W) 
max_buy_energy_per_period = 1700        # (Wh), debido a la máxima potencia contratada con la red max_grid_power(W)
charge_efficiency = 0.9   # Eficiencia de carga de la batería
discharge_efficiency = 0.85 # Eficiencia de descarga de la batería

# current_datetime= datetime.now() - timedelta(minutes=48)
current_datetime= datetime.now().replace(minute=55, second=0, microsecond=0)

######### START: Zona para pegar los valores del Markdown en HA
initial_soc= 1070.08
min_soc= 896.0

demand= [270, 249, 197, 149, 135, 154, 180, 2000, 177, 159, 146, 270, 249, 197, 149, 135, 154, 180, 189, 177, 159, 146]

solar_production= [221, 232, 228, 209, 221, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

buy_prices= [0.19038, 0.14314, 0.15878, 0.17599, 0.17943, 0.23389, 0.2472, 0.24823, 0.23227, 0.17937, 0.16455, 0.19038, 0.14314, 0.15878, 0.17599, 0.17943, 0.23389, 0.2472, 0.24823, 0.23227, 0.17937, 0.16455]

sell_prices= [0.08262, 0.08449, 0.09538, 0.11132, 0.11525, 0.12025, 0.13115, 0.13258, 0.11896, 0.11516, 0.0992, 0.08262, 0.08449, 0.09538, 0.11132, 0.11525, 0.12025, 0.13115, 0.13258, 0.11896, 0.11516, 0.0992]

######### END: Zona para pegar los valores del Markdown en HA

num_hours = len(demand)
buy_prices= [round(1*x, 5) for x in buy_prices]
# Battery cost parameters
battery_purchase_price=1000  # €
battery_eol_cycles_if_min_soc_20=3500  # cycles
battery_eol_cycles_if_min_soc_50=7000  # cycles
min_soc_percent= min_soc / battery_capacity *100 # %
# Linear interpolation between 20% and 50% to estimate the battery lifetime at min_soc_percent
battery_eol_cycles_current_min_soc = battery_eol_cycles_if_min_soc_20 + \
    (battery_eol_cycles_if_min_soc_50 - battery_eol_cycles_if_min_soc_20) * (min_soc_percent - 20) / 30  # cycles

# Battery energy cost. Only considered when discharging the battery
# In its lifetime, the battery can provide:
all_live_energy= (battery_eol_cycles_current_min_soc*battery_capacity*(100-min_soc_percent)/100)/1000 # kWh of energy

# Therefore, the cost of the energy from battery is battery_purchase_price / all_live_energy €/kWh
battery_energy_price = battery_purchase_price / all_live_energy  # €/kWh

# Take into account the time remaining until the end of the current hour
max_charge_energy_first_period = max_charge_energy_per_period - (current_datetime.minute * max_charge_energy_per_period / 60)
max_discharge_energy_first_period = max_discharge_energy_per_period - (current_datetime.minute * max_discharge_energy_per_period / 60)
max_buy_energy_first_period = max_buy_energy_per_period - (current_datetime.minute * max_buy_energy_per_period / 60)
demand[0] = demand[0] - (current_datetime.minute * demand[0] / 60)
solar_production[0] = solar_production[0] - (current_datetime.minute * solar_production[0] / 60)

# Suma de la demanda y la producción solar
total_demand = sum(demand)
total_solar_production = sum(solar_production)

# Precio medio de la electricidad
average_price = sum(buy_prices) / num_hours
# Precio máximo de la electricidad
max_price = max(buy_prices)

print()
print(f"Optimization for next {num_hours} hours")
print(f"Battery capacity: {battery_capacity} Wh")
print(f"Initial SoC: {initial_soc:.2f} Wh ({initial_soc/battery_capacity*100:.2f} %)")
print(f"Minimum SoC: {min_soc:.2f} Wh ({min_soc/battery_capacity*100:.2f} %)")
print(f"Current datetime: {current_datetime}")
print(f"Max charge energy in the first period: {max_charge_energy_first_period:.2f} Wh")
print(f"Max discharge energy in the first period: {max_discharge_energy_first_period:.2f} Wh")
print(f"Max buy energy in the first period: {max_buy_energy_first_period:.2f} Wh")
print(f"Energy demand in the first period: {demand[0]:.2f} Wh")
print(f"Solar production in the first period: {solar_production[0]:.2f} Wh")
print(f"max_charge_energy_per_period: {max_charge_energy_per_period:.2f} Wh")
print(f"max_discharge_energy_per_period: {max_discharge_energy_per_period:.2f} Wh")
print(f"max_buy_energy_per_period: {max_buy_energy_per_period:.2f} Wh")
print(f"grid average_price: {average_price:.4f} €/kWh")
print(f"battery_energy_price: {battery_energy_price:.4f} €/kWh")
print(f"all_live_energy: {all_live_energy:.2f} kWh")
print(f"battery_eol_cycles_current_min_soc: {battery_eol_cycles_current_min_soc:.2f} cycles")

# Establecer el peso que daremos en la función objetivo a maximizar el SoC final frente a minimizar el coste de la energía comprada
# Cuando la producción solar es mayor que la demanda, se primará maximizar el SoC
if total_solar_production >= total_demand:
    w=2*average_price/1000
    #w=2*max_price/1000
    print(f"¡Solar production covers all demand! w={w}")
    
else:
    w= average_price/1000
    #w=20*max_price/1000
    print(f"¡Solar production does not cover all demand! w={w}")

# NO NECESARIO: EL PROBLEMA SE RESUELVE CORRECTAMENTE AUNQUE initial_soc < min_soc

# Crear el problema de optimización
problem = pulp.LpProblem("Optimal_SOC_with_Cost_Minimization", pulp.LpMinimize)

# Variables de decisión: energía comprada y SoC de la batería en cada hora
energy_from_grid = [pulp.LpVariable(f'f_grid_{i}', lowBound=0, upBound=max_buy_energy_per_period) for i in range(num_hours)]
energy_to_grid = [pulp.LpVariable(f't_grid_{i}', lowBound=0) for i in range(num_hours)]
soc = [pulp.LpVariable(f'soc_{i}', lowBound=0, upBound=battery_capacity) for i in range(num_hours)]
energy_to_battery = [pulp.LpVariable(f'charge_{i}', lowBound=0, upBound=max_charge_energy_per_period) for i in range(num_hours)]
energy_from_battery = [pulp.LpVariable(f'discharge_{i}', lowBound=0, upBound=max_discharge_energy_per_period) for i in range(num_hours)]

# Función objetivo: minimizar el coste de la energía comprada mientras maximizamos el SoC final
buy_cost = pulp.lpSum([(energy_from_grid[i] * buy_prices[i] + \
                        energy_from_battery[i] * battery_energy_price - \
                        energy_to_grid[i] * sell_prices[i] - \
                        energy_to_battery[i] * battery_energy_price \
                        )*(1/1000) \
                        for i in range(num_hours)])  # Convertir preciosa €/Wh
final_soc = soc[-1]  # El estado de carga al final del periodo
problem += buy_cost - w * final_soc   # Minimizar el coste y maximizar el SoC final, ponderando la decisión con w (€/Wh que dan valor a la energía almacenada)

# RESTRICCIONES
# Exigir que el SoC en el último periodo se mayor que el SoC inicial.
# Se podría haber establecido el SoC final como un parámetro de entrada. Plantearlo en futuras versiones
problem += soc[-1] >= initial_soc

for i in range(num_hours):

    # Establecer el SoC al final de cada periodo periodo soc[i]: 
    if i == 0:
        # En la primera hora, se parte de initial_soc y se hace balance
        problem += soc[i] == initial_soc + energy_to_battery[i] - energy_from_battery[i]
        problem += energy_to_battery[i] <= max_charge_energy_first_period
        problem += energy_from_battery[i] <= max_discharge_energy_first_period
        problem += energy_from_grid[i] <= max_buy_energy_first_period
        # Analizar cuanta energía se podría enviar a la batería en el primer periodo por si el soc inicial es menor que el min_soc
        max_energy_available = max(max_buy_energy_first_period + solar_production[0] - demand[0],0)
        print(f"First period max energy available: {max_energy_available:.2f}")
        max_energy_to_battery = min(max_charge_energy_first_period, max_energy_available*charge_efficiency)
        print(f"First period max energy to battery: {max_energy_to_battery:.2f}")
        # Exigir que el SoC no baje de min_soc si es posible, o recuperarlo lo más rápido posible
        if initial_soc < min_soc:
            problem += soc[i] >= initial_soc + max_energy_to_battery
            print("Initial SoC is lower than min_soc. Charging the battery with the available energy. Condition is: " \
                  , initial_soc+max_energy_to_battery)
        else:
            # Exigir que el SoC no baje de min_soc
            problem += soc[i] >= min_soc      
    else:
        # En las horas siguientes, el SoC depende del estado anterior
        problem += soc[i] == soc[i - 1] + energy_to_battery[i] - energy_from_battery[i]
        # Exigir que el SoC no baje de min_soc
        problem += soc[i] >= min_soc        

    # Balance de energía global
    problem += demand[i] + pulp.lpSum(energy_to_battery[i])/charge_efficiency + energy_to_grid[i] == \
        energy_from_grid[i] + solar_production[i] + pulp.lpSum(energy_from_battery[i]) * discharge_efficiency

# Resolvemos el problema
problem.solve()
print()

# Verificar el estado de la solución
status = pulp.LpStatus[problem.status]
print(f"Estado de la solución: {status}")

# Resultados
total_grid_cost=0
for i in range(num_hours):
    total_grid_cost+=energy_from_grid[i].varValue*buy_prices[i]/1000 - energy_to_grid[i].varValue*sell_prices[i]/1000

print(f"Función objetivo: {pulp.value(problem.objective):.2f} €")
print(f"Estado de carga final: {soc[-1].varValue:.2f} Wh")
print(f"Importe de la electricidad comprada a la red: {total_grid_cost:.2f} €")
# Crear un DataFrame con los resultados
results = pd.DataFrame({
    'Hour': range(1, num_hours + 1),
    'buy_price(€/kWh)': buy_prices,
    'sell_price(€/kWh)': sell_prices,
    'Demand(Wh)': demand,
    'from_solar(Wh)': solar_production,
    'from_grid(Wh)': [round(energy_from_grid[i].varValue) for i in range(num_hours)],
    'to_grid(Wh)': [round(energy_to_grid[i].varValue) for i in range(num_hours)],
    'to_battery(Wh)': [round(energy_to_battery[i].varValue) for i in range(num_hours)],
    'from_battery(Wh)': [round(energy_from_battery[i].varValue) for i in range(num_hours)],
    'SoC(Wh)': [round(soc[i].varValue) for i in range(num_hours)],
    'SoC(%)': [round(soc[i].varValue/battery_capacity*100) for i in range(num_hours)]
})

# Exportar los resultados a CSV
results.to_csv('results.csv', index=False)
problem.writeLP("Optimal_SOC_with_Cost_Minimization.lp") 

