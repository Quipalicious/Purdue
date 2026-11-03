"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     12.1.2
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import numpy as np
import matplotlib.pyplot as plt

def main():
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2.1, 3.9, 6.2, 7.8, 10.1])

    plt.figure(figsize=(8,6))
    plt.scatter(x, y, edgecolors="black", s=80, label="Sample Data", color="black")

    plt.title("Sample Data")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.grid(True, "both")

    a, b = np.polyfit(x, y, 1)
    y_predict = x * a + b

    sse = np.sum((y_predict - y)**2)
    sst = np.sum((y - y.mean())**2)
    r2 = 1 - (sse/sst)

    x_reg = np.linspace(x.min(), x.max(), 100)
    y_reg = x_reg * a + b

    plt.plot(x_reg, y_reg, color="red", label=f"Regression: y = {a:.3f}x + {b:.3f}, r^2={r2:.3f}")
    plt.title("Linear Regression Fit")
    plt.legend(fontsize=12)

    #plt.savefig("plot.png")

    print("Slope (m): "+str(round(a, 3)))
    print("Intercept (b): "+str(round(b, 3)))
    print("Model: y = "+str(round(a, 3))+"x + "+str(round(b, 3)))
    print("r^2: "+str(round(r2, 3)))


if __name__ == "__main__":
    main()
