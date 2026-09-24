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

##TEST
comparisonMatrix = [
    [1,9,1/9],
    [1/9,1,9],
    [9,1/9,1],
]


weights,eigenvalue = ahp(comparisonMatrix)

CR, valid = consistency_ratio(eigenvalue, comparisonMatrix, threshold)

print("Weights: ")
print(weights)

print("\nDominant eigenvalue: ")
print(eigenvalue)

if valid:
    print("Matrix is consistent")
else:
    print("Matrix is inconsistent")


