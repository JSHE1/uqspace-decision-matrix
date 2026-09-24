#file: UqSpace-DMM
#purpose: Automates the Refined DMM
#Version 1: Backend Calculations
#Version 1: AHP calculations, TOPSIS calculations
#last edited: 01/09/2026
#editor: Jamie

import numpy as np
#initialise a global variable CR
#sets default CR = 0, allows for 0 CR to be provided
threshold = 0


################# AHP ##########################################

#function: ahp
#param: matrix , Matrix containing critera and criterion
#return: weights , integer
#return: dominantEigenvalue , array (matrix) 
def ahp(matrix):
    #init matrix containing param, holding floats
    matrix = np.array(matrix, dtype=float)

    #Calculate eigenvalues and vectors
    eigenvalues, eigenvectors = np.linalg.eig(matrix)

    #Calculate the dominant eigenvalue
    maxIndex = np.argmax(eigenvalues.real)

    dominantEigenvalue = eigenvalues[maxIndex].real
    dominantEigenvector = eigenvectors[:, maxIndex].real

    #Normalise the vectors such that the sum is equal to 1
    weights = dominantEigenvector / dominantEigenvector.sum()

    return weights, dominantEigenvalue

#function: saaty_random_index
#param: matrix, Matrix containing criteria and criterion
#return RI , float containing the relative index of a matrix
def saaty_random_index(matrix):
    #init matrix containing param, holding floats
    matrix = np.array(matrix, dtype=float)
    
    #init size of matrix/ argument count
    n = matrix.shape[0]

    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Error M-02: AHP comparison matrix must be square")

    #Saaty relative index 
    RI = [0.00,0.00,0.00,0.58,0.90,
          1.12,1.24,1.32,1.41,1.45,1.49]

    #check for matrix of size too large
    if n >= len(RI):
        raise ValueError("Error M-01: Saaty RI not available for this matrix size.")
    
    #return the relative index
    return RI[n]

#function: consistency_ratio
#param: domEigval , float the dominant eigenvale
#param: matrix , Matrix containing criteria and criterion
#param: CR, float chosen Consistency Ratio
def consistency_ratio(domEigval, matrix, threshold):
    #init matrix containing param, holding floats
    matrix = np.array(matrix, dtype=float)
    
    #check CR != NULL
    if threshold == 0:
    #spec mentions 0.1 to be the default CR
        threshold = 0.1

    #grab the number of args
    n = matrix.shape[0]

    #n <=2 is always consistent
    if n<=2:
        return 0.0,True

    #calculate comparison index
    CI = (domEigval - n) / (n - 1)

    #calculate random index
    RI = saaty_random_index(matrix)

    #calculate the CR of the matrix
    CR = CI/RI
    
    is_consistent = CR < threshold

    return CR, is_consistent

################ TOPSIS ########################################

#function: normalise_matrix
#param: matrix, Matrix containing criteria and criterion
#param: weights , integer
#return: weighted, normalised values.
def normalise_matrix(matrix, weights):
    matrix = np.array(matrix, dtype = float)
    weights = np.array(weights, dtype = float)

    norms = np.sqrt(np.sum(matrix ** 2, axis=0))

    normalised = matrix / norms

    weighted = normalised*weights

    return weighted

#function ideal_solutions
#param: weighted , the weighted and normalised matrix
#param: benefit , an array of bools where true is btter and false is lower
#return: idealBest , array (s+)
#return: idealWorst , array (s-)
def ideal_solutions(weighted, benefit):
    weighted = np.array(weighted, dtype = float)
    benefit = np.array(benefit, dtype = bool)

    colMax = weighted.max(axis=0)
    colMin = weighted.min(axis=0)

    idealBest = np.where(benefit,colMax,colMin)
    idealWorst = np.where(benefit,colMin,colMax)

    return idealBest, idealWorst

#function separation_distances
#param: weighted
#param: idealBest
#param: idealWorst
def separation_distances(weighted, idealBest, idealWorst):
    weighted=  np.array(weighted, dtype=float)

    dBest = np.sqrt(np.sum((weighted - idealBest)**2, axis = 1))
    dWorst = np.sqrt(np.sum((weighted - idealWorst)**2, axis = 1))

    return dBest, dWorst

def closeness_coefficient(dBest, dWorst):
    total = dBest + dWorst

    C = np.divide(dWorst, total, out=np.full_like(total,0.5),where=total != 0)

    return C

def topsis(matrix, weights, benefit):
    matrix = np.array(matrix, dtype=float)
    weights = np.array(weights, dtype=float)
    benefit = np.array(benefit, dtype=float)

    #rough check on invalid params
    if matrix.ndim != 2:
        raise ValueError("Error T-01: decision matrix must be 2D")
    m,n = matrix.shape
    if len(weights) != n:
        raise ValueError("Error T-02: number of weights must equal number of criteria")
    if len(benefit) != n:
        raise ValueError("Error T-03: number of benefit flags must equal number of criteria")
    if m < 2:
        raise ValueError("Error T-04: TOPSIS needs atleast 2 alternatives")

    weighted = normalise_matrix(matrix, weights)
    idealBest, idealWorst = ideal_solutions(weighted, benefit)
    dBest, dWorst = separation_distances(weighted, idealBest, idealWorst)
    C = closeness_coefficient(dBest, dWorst)

    ## highest to lowest closeness
    ranking = np.argsort(-C)

    return C, ranking
    
    
    

#the big boy topsis!


##TEST

if __name__ == "__main__":
    
    comparisonMatrix = [
        [1,9,1/9],
        [1/9,1,9],
        [9,1/9,1],
    ]


    weights,eigenvalue = ahp(comparisonMatrix)

    CR, valid = consistency_ratio(eigenvalue, comparisonMatrix, threshold)

    ## TEST 1:
    print("TEST 1")
    print("Weights:", np.round(weights, 3))
    print("Dominant eigenvalue:", round(eigenvalue, 3))
    print("CR:", round(CR,3), "->", "consistent" if valid else "incon")

    ## TEST 2:
    specMatrix = [
        [1, 1/7, 1/9, 1/4, 1/2],
        [7, 1, 1, 3, 4],
        [9, 1, 1, 3, 6],
        [4, 1/3, 1/3, 1, 2],
        [2, 1/4, 1/6, 1/2, 1],
    ]

    weights, eigenvalue = ahp(specMatrix)
    CR, valid = consistency_ratio(eigenvalue, specMatrix, threshold)
    print("\nTEST 2")
    
    print("Weights (%):", np.round(weights *100,1))
    print("CR:", round(CR, 3), "->", "consistent" if valid else "inconsistent")

    # add solutions to spec table
    names = ["Design A", "Design B", "Design C"]
    decisionMatrix = [
        #deisgn A e.g.
        #cost|Weight|Perfom|Manufact|Resuse
        [1200, 4.5, 850, 0.5, 0.3],
        #design B
        #cost|Weight|Perfom|Manufact|Resuse
        [900, 5.2, 780, 0.3, 0.5],
        #design C
        #cost|Weight|Perfom|Manufact|Resuse
        [1500, 3.9, 920, 0.2, 0.2],
    ]

    #criteria scaling
    # so like if its cost we obv want it lower so FALSE
    # but for say performance we probablt want that higher so TRUE
    benefit = [False, False, True, True, True]

    C, ranking = topsis(decisionMatrix, weights, benefit)
    print("\nTest 3: TOPSIS")
    for rank, i in enumerate(ranking,start =1):
        print(f"{rank}. {names[i]}: C = {C[i]:.3f}")
    
