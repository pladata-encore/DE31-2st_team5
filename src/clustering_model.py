import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
import cupy as cp
#from sklearn.decomposition import IncrementalPCA
from cuml import IncrementalPCA
from umap import UMAP
#from cuml.manifold import UMAP
from sklearn.metrics import silhouette_score
from line_profiler import profile
from log import log

@profile
def clustering_model(similarity_matrix):
    # 코사인 유사도 행렬의 대각선을 1로 채워줌.
    np.fill_diagonal(similarity_matrix, 1)

    # 거리 행렬로 변환
    distance_matrix = 1 - similarity_matrix
    
    # 거리 행렬을 대칭 행렬로 만들기 위해 아래와 같이 대칭행렬로 변환
    distance_matrix_symmetric = (distance_matrix + distance_matrix.T) / 2
    
    # 음수 값을 0으로 만들어줌
    distance_matrix_symmetric[distance_matrix_symmetric < 0] = 0
    
    # 행렬로 변환
    condensed_distance = squareform(distance_matrix_symmetric)
    
    # 계층적 병합 클러스터링 
    z = linkage(condensed_distance, method='ward')
    
    return z

@profile
def retrieve_fcluster(Z, min_clusters: int, max_clusters: int, data_points: np.ndarray):
    """
    계층적 클러스터링 결과에서 최적의 클러스터 개수를 결정하고 해당 클러스터링 결과를 반환하는 함수

    Parameters:
        Z (np.ndarray): 계층적 클러스터링 결과 배열
        min_clusters (int): 최소 클러스터 개수
        max_clusters (int): 최대 클러스터 개수
        data_points (np.ndarray): 클러스터링 평가를 위한 데이터 포인트

    Returns:
        np.ndarray: 최적의 클러스터링 결과 배열
        int: 최적의 클러스터 개수
        float: 최고 실루엣 점수

    계층적 클러스터링 결과에서 최적의 클러스터 개수를 결정하고 해당 클러스터링 결과를 반환
    """
    best_num_clusters = min_clusters
    best_silhouette_score = -1
    best_clusters = None
    
    for num_clusters in range(min_clusters, max_clusters + 1):
        clusters = fcluster(Z, num_clusters, criterion='maxclust')
        num_unique_clusters = len(np.unique(clusters))
        if num_unique_clusters == num_clusters:
            try:
                silhouette_avg = silhouette_score(data_points, clusters)
                if silhouette_avg > best_silhouette_score:
                    best_silhouette_score = silhouette_avg
                    best_num_clusters = num_clusters
                    best_clusters = clusters
            except Exception as e:
                log(f"Exception occurred during silhouette scoring: {e}", 1)
                continue

    return best_clusters, best_num_clusters

@profile
def reduce_dimensions(tfidf_matrix):
    """
    TF-IDF 행렬을 사용하여 2차원 데이터 포인트로 차원 축소를 수행.

    TF-IDF 행렬 -> IPCA -> UMAP -> datapoints

    Parameters:
    tfidf_matrix (scipy.sparse.csr.csr_matrix): TF-IDF 행렬.

    Returns:
    numpy.ndarray: (n, 2) 크기의 2차원 데이터 포인트 배열.
    
    각 데이터포인트는 원래의 고차원 TF-IDF 특성을 저차원 공간에서 표현한 것으로, 문서간의 유사성을 시각적으로 비교할 수 있음.
    """
    
    # 로그 메시지 출력
    log("Starting dimension reduction...")
    
    log("Performing IPCA initialization...")
    # IPCA 초기화
    ipca = IncrementalPCA(n_components=50, batch_size=1000)
    # 데이터를 배치로 나누어 IPCA 수행
    ipca_result = ipca.fit_transform(tfidf_matrix)
    
    # UMAP 수행
    log("Applying UMAP...")
    umap_model = UMAP(n_components=2)
    #umap_model.fit(cp.asarray(ipca_result))
    #data_points = umap_model.transform(cp.asarray(ipca_result))
    data_points = umap_model.fit_transform(ipca_result)
    log("Dimension reduction completed.")
    return data_points

@profile
def get_cluster_documents(df, clusters, cluster_num):
    """
    특정 클러스터에 속하는 문서들의 내용을 반환하는 함수
    
    Parameters:
    - df (DataFrame): 문서 데이터프레임
    - clusters (array): 각 문서에 할당된 클러스터 번호 배열
    - cluster_num (int): 확인하고자 하는 클러스터 번호
    
    Returns:
    - 해당 클러스터에 속하는 문서들의 내용 리스트
    """
    
    cluster_indices = [idx for idx, cluster in enumerate(clusters) if cluster == cluster_num]
    cluster_documents = df.iloc[cluster_indices]['docKey'].tolist()
    return cluster_documents