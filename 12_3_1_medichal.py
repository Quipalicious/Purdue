"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     12.3.1
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def main():
    CSV_name = "river_data.csv"

    data = pd.read_csv(CSV_name)
    
    print("--- WABASH RIVER AUTHORITY: Water Quality Dataset ---\n")
    print(data)

    print("\n--- SUMMARY STATISTICS ---\n")

    data_stats = {'temp_c': pd.Series(data['temp_c'].describe(),
                                        index=['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']),
                                        'do_mg_l': pd.Series(data['do_mg_l'].describe(),
                                        index=['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']),
                                        'ph': pd.Series(data['ph'].describe(),
                                        index=['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max'])}

    data_stats = pd.DataFrame(data_stats)

    print(data_stats)
    print("\n--- LINEAR REGRESSION RESULTS ---\n")

    x = data['temp_c']
    y = data['do_mg_l']

    a, b = np.polyfit(x, y, 1)

    y_reg = a * x + b

    sse = np.sum((y - y_reg)**2)
    sst = np.sum((y - np.mean(y))**2)
    r2 = 1 - (sse / sst)

    print(f"Slope: {a:.3f} mg/L per deg C")
    print(f"Intercept: {b:.3f} mg/L")
    print(f"SSE: {sse:.3f} (mg/L)^2")
    print(f"SST: {sst:.3f} (mg/L)^2")
    print(f"r^2: {r2:.3f}")

    data_a = data[data['site'] == 'A']
    data_b = data[data['site'] == 'B']
    data_c = data[data['site'] == 'C']

    x_a = data_a[['temp_c']]
    y_a = data_a[['do_mg_l']]
    x_b = data_b[['temp_c']]
    y_b = data_b[['do_mg_l']]
    x_c = data_c[['temp_c']]
    y_c = data_c[['do_mg_l']]

    plt.figure(figsize=(8,6))
    plt.scatter(x_a, y_a, s=80, color="red", label="Upstream", marker="^")
    plt.scatter(x_b, y_b, s=80, color="blue", label="Midstream", marker="v")
    plt.scatter(x_c, y_c, s=80, color="green", label="Downstream", marker="s")

    plt.title("Temperature vs Oxygen Concentration")
    plt.xlabel("Water Temperature (Celsius)")
    plt.ylabel("Dissolved Oxygen Concentration (mg/L)")
    plt.legend(loc="best")

    plt.savefig("12_3_1_do_temp_plot_medichal.png")

    plt.plot(x, y_reg, color="black")
    plt.savefig("12_3_1_do_temp_regression_plot_medichal.png")




if __name__ == "__main__":
    main()
