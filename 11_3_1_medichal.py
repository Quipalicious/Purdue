"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     11.3.1
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import pandas as pd
import matplotlib.pyplot as plt

def main():
    CSV_name = "data_NYC_elevators.csv"
    elev_df = pd.read_csv(CSV_name)


    print("NYC Elevator Data (First 10 rows):")
    print(elev_df.iloc[0:10].to_string(show_dimensions=False))

    print("\nColumn names:")
    print(elev_df.columns)

    print("\nShape (rows, columns): "+str(elev_df.shape))

    elev_df = elev_df.rename(columns={'LATITUDE (decimal degrees)':'Latitude', 'LONGITUDE (decimal degrees)':'Longitude'})

    
    plt.figure(figsize=(8,6))
    plt.scatter(elev_df['Latitude'], elev_df['Longitude'], c='blue', s=10)
    plt.axis('equal')
    plt.savefig('11_3_1_nyc_elevator_map_username.png')

    max_bound = elev_df['Longitude'].mean() + (6*elev_df['Longitude'].std())
    min_bound = elev_df['Longitude'].mean() - (6*elev_df['Longitude'].std())

    elev_df = elev_df[(elev_df['Longitude'] >= min_bound)&(elev_df['Longitude'] <= max_bound)]

    plt.figure(figsize=(10,8))
    plt.scatter(elev_df['Latitude'], elev_df['Longitude'], c='green', s=1)
    plt.axis('equal')
    plt.savefig('11_3_1_nyc_elevator_map_revised_username.png')

    man_elev_df = elev_df.loc[((elev_df['ZIP_CODE']>=10001) & (elev_df['ZIP_CODE']<=10075)) | (elev_df['ZIP_CODE']==10128) | (elev_df['ZIP_CODE']==10280)]

    plt.figure(figsize=(10,8))
    plt.scatter(man_elev_df['Latitude'], man_elev_df['Longitude'], c='purple', s=1)
    plt.axis('equal')
    plt.savefig('11_3_1_manhattan_elevator_map_username.png')
    
    print("\nFirst 5 rows (Manhattan):")
    print(man_elev_df.iloc[0:5])
    print("\nThe number of elevators in Manhattan is "+str(len(man_elev_df))+".")

    man_elev_df.to_csv('11_3_1_manhattan_elevator_data_username.csv')
if __name__ == "__main__":
    main()
