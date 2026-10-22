"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     11.1.2
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import csv
import time
import numpy as np
import pandas as pd


def main():
    CSV_PATH = "metal_mass_volume.csv"


    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("Original Data - For Loop: \n\n" + str(rows) + "\n")

    density_loop = []

    start = time.perf_counter()
    for i in rows:
        density_loop.append(round(float(i["Mass_g"]) / float(i["Volume_cm3"]), 1))
    end = time.perf_counter()
    loop_time = end - start

    print("Density (Loop): \n\n" + str(density_loop) + "\n")
    print("Loop execution time (s): "+ str(round(loop_time, 6)) + "\n\n")


    numpy_df = pd.read_csv(CSV_PATH)

    print("Original Data - NumPy: \n\n" + str(numpy_df) + "\n")

    mass_np = np.array(numpy_df["Mass_g"])
    volume_np = np.array(numpy_df["Volume_cm3"])

    start = time.perf_counter()
    density_np = mass_np / volume_np
    end = time.perf_counter()
    numpy_time = end - start

    print("Density (numpy): \n\n" + str(density_np) + "\n")
    print("Numpy execution time (s): "+ str(round(numpy_time, 6)) + "\n\n")


    pandas_df = pd.read_csv(CSV_PATH)

    print("Original Data - Pandas: \n\n" + str(pandas_df) + "\n")

    start = time.perf_counter()
    pandas_df["Density_g/cm3"] = round(pandas_df["Mass_g"] / pandas_df["Volume_cm3"], 1)
    end = time.perf_counter()
    pandas_time = end - start

    print("Density (Pandas): \n\n" + str(pandas_df) + "\n")
    print("Numpy execution time (s): "+ str(round(pandas_time, 6)) + "\n")

    print("Equivalence Checks: \n")

    print("type(mass_np): " + str(type(mass_np)))
    print("mass.dtype(): " + str(mass_np.dtype))
    print("type(pandas_df[\"Mass_g\"].values): " + str(type(pandas_df["Mass_g"].values)) + "\n")

    print("mass arrays equal (NumPy vs pandas): " + str(np.array_equal(mass_np, pandas_df["Mass_g"].to_numpy())))
    print("dtype match (pandas vs NumPy): " + str(mass_np.dtype == pandas_df["Mass_g"].dtype))
    print("density values allclose (NumPy vs pandas): " + str(np.allclose(mass_np, pandas_df["Mass_g"])) + "\n")

    print("Sorted by Density (pandas): \n")

    sorted_pd = pandas_df.sort_values(by="Density_g/cm3")
    print(sorted_pd)

    print("\nSorted Density (NumPy array): \n")

    sorted_np = np.sort(density_np)
    print(sorted_np)

    mass_np[0] = np.nan
    pandas_df.at[0, "Mass_g"] = np.nan

    
    density_np = mass_np / volume_np
    print("\nDensity with Missing Mass (NumPy): \n\n" + str(density_np) + "\n")
    
    pandas_df["Density_g/cm3"] = round(pandas_df["Mass_g"] / pandas_df["Volume_cm3"], 1)
    print("Density with Missing Mass (Pandas): \n\n" + str(pandas_df) + "\n")

    print("NaN detected via pandas .isna(): " + str(("True" in str(pandas_df['Density_g/cm3'].isna()))))


if __name__ == "__main__":
    main()
