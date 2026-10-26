"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     11.1.3
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

def main():
    CSV_name = "mild_steel_stress_strain.csv"

    data = pd.read_csv(CSV_name)

    print("--- Mild Steel Stress-Strain Data ---\n")
    print(data.iloc[0:5])

    stress_mean = data["stress_MPa"].mean()
    stress_median = data["stress_MPa"].median()
    stress_stdev = data["stress_MPa"].std()
    stress_min = data["stress_MPa"].min()
    stress_max = data["stress_MPa"].max()

    strain_mean = data["strain_percent"].mean()
    strain_median = data["strain_percent"].median()
    strain_stdev = data["strain_percent"].std()
    strain_min = data["strain_percent"].min()
    strain_max = data["strain_percent"].max()

    print("\nMean stress: "+str(round(stress_mean, 2))+" MPa")
    print("Median stress: "+str(round(stress_median, 2))+" MPa")
    print("Standard deviation of stress: "+str(round(stress_stdev, 2))+" MPa")
    print("Min stress: "+str(round(stress_min, 2))+" MPa")
    print("Max stress: "+str(round(stress_max, 2))+" MPa\n")

    print("Mean strain: "+str(round(strain_mean, 2))+" %")
    print("Median strain: "+str(round(strain_median, 2))+" %")
    print("Standard deviation of strain: "+str(round(strain_stdev, 2))+" %")
    print("Min strain: "+str(round(strain_min, 2))+" %")
    print("Max strain: "+str(round(strain_max, 2))+" %")

    
    plt.plot(data["stress_MPa"], data["strain_percent"], "bo-")
    plt.title("Mild Steel Stress-Strain Curve", fontsize=14, pad=15)
    plt.xlabel("Strain (%)", fontsize=12, labelpad=10)
    plt.ylabel("Stress (MPa)", fontsize=12, labelpad=10)

    plt.gca().xaxis.set_major_formatter(PercentFormatter(100))
    plt.xlim(0,45)
    plt.ylim(0, 500)

    plt.tick_params(labelsize=12)
    plt.grid(True)
    plt.minorticks_on()



if __name__ == "__main__":
    main()
