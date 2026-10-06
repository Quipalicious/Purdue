"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     9.3.1
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import math as m


def main():
    print("""Select a tool:
    1) Irrigation System Check
    2) Escape Velocity Calculator""")
    choice = int(input("Enter choice (1 or 2): "))

    if choice == 1:
        irrigation_check()
    elif choice == 2:
        escape_velocity_calc()
    else:
        main()


def irrigation_check():
    moisture = float(input("Enter soil moisture (%, 0-60): "))
    rain = float(input("Enter forecasted rain (mm, 0-50): "))
    pressure = "".join(input("Is the system experiencing low pressure? (yes/no): ").split()).lower()
    maintenance = "".join(input("Is maintenance needed? (yes/no): ").split()).lower()

    if pressure == "yes":
        pressure = True
    elif pressure == "no":
        pressure = False
    else:
        pressure = False
        print("WARNING - Did not receive readable input - Pressure automatically set as normal")

    if maintenance == "yes":
        maintenance = True
    elif maintenance == "no":
        maintenance = False
    else:
        maintenance = False
        print("WARNING - Did not receive readable input - Maintenance automatically set as normal")

    print("")

    if maintenance:
        print("DO NOT IRRIGATE - maintenance required.")
    elif pressure:
        print("DO NOT IRRIGATE - low pressure condition.")
    elif rain >= 10:
        print("DELAY - significant rainfall expected.")
    elif moisture < 20:
        print("RUN FULL")
    elif (moisture >= 20 and moisture <= 25):
        print("RUN REDUCED")
    elif moisture >= 25:
        print("SKIP - soil moisture is adequate.")


def escape_velocity_calc():
    density = float(input("Enter the density of the planet (kg/m^3): "))
    radius = float(input("Enter the radius of the planet (m): "))
    G = 6.6743 * 10**-11

    volume = 4 / 3 * m.pi * (radius**3)
    mass = density * volume
    escape_velocity = m.sqrt(2 * G * mass / radius)

    print("")
    print("---Calculator Results---")
    print("Planet radius: " + str(round(radius/1000, 2)) + " km")
    print("Escape velocity: " + str(round(escape_velocity, 2)) + " m/s")



if __name__ == "__main__":
    main()
