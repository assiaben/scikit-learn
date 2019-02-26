# Authors: Shane Grigsby <refuge@rocktalus.com>
#          Amy X. Zhang <axz@mit.edu>
# License: BSD 3 clause

import numpy as np
import pytest

from sklearn.datasets.samples_generator import make_blobs
from sklearn.cluster.optics_ import OPTICS
from sklearn.metrics.cluster import contingency_matrix
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.cluster.dbscan_ import DBSCAN
from sklearn.utils.testing import assert_equal, assert_warns
from sklearn.utils.testing import assert_array_equal
from sklearn.utils.testing import assert_raise_message
from sklearn.utils.testing import assert_allclose

from sklearn.cluster.tests.common import generate_clustered_data


rng = np.random.RandomState(0)
n_points_per_cluster = 10
C1 = [-5, -2] + .8 * rng.randn(n_points_per_cluster, 2)
C2 = [4, -1] + .1 * rng.randn(n_points_per_cluster, 2)
C3 = [1, -2] + .2 * rng.randn(n_points_per_cluster, 2)
C4 = [-2, 3] + .3 * rng.randn(n_points_per_cluster, 2)
C5 = [3, -2] + 1.6 * rng.randn(n_points_per_cluster, 2)
C6 = [5, 6] + 2 * rng.randn(n_points_per_cluster, 2)
X = np.vstack((C1, C2, C3, C4, C5, C6))


def test_correct_number_of_clusters():
    # in 'auto' mode

    n_clusters = 3
    X = generate_clustered_data(n_clusters=n_clusters)
    # Parameters chosen specifically for this task.
    # Compute OPTICS
    clust = OPTICS(max_eps=5.0 * 6.0, min_samples=4)
    clust.fit(X)
    # number of clusters, ignoring noise if present
    n_clusters_1 = len(set(clust.labels_)) - int(-1 in clust.labels_)
    assert_equal(n_clusters_1, n_clusters)

    # check attribute types and sizes
    assert clust.labels_.shape == (len(X),)
    assert clust.labels_.dtype.kind == 'i'

    assert clust.reachability_.shape == (len(X),)
    assert clust.reachability_.dtype.kind == 'f'

    assert clust.core_distances_.shape == (len(X),)
    assert clust.core_distances_.dtype.kind == 'f'

    assert clust.ordering_.shape == (len(X),)
    assert clust.ordering_.dtype.kind == 'i'
    assert set(clust.ordering_) == set(range(len(X)))


def test_minimum_number_of_sample_check():
    # test that we check a minimum number of samples
    msg = ("Number of training samples (n_samples=1) must be greater than "
           "min_samples (min_samples=10) used for clustering.")

    # Compute OPTICS
    X = [[1, 1]]
    clust = OPTICS(max_eps=5.0 * 0.3, min_samples=10)

    # Run the fit
    assert_raise_message(ValueError, msg, clust.fit, X)


def test_bad_extract():
    # Test an extraction of eps too close to original eps
    msg = "Specify an epsilon smaller than 0.15. Got 0.3."
    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # Compute OPTICS
    clust = OPTICS(max_eps=5.0 * 0.03,
                   cluster_method='dbscan',
                   eps=0.3, min_samples=10)
    assert_raise_message(ValueError, msg, clust.fit, X)


def test_bad_reachability():
    msg = "All reachability values are inf. Set a larger max_eps."
    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    with pytest.warns(UserWarning, match=msg):
        clust = OPTICS(max_eps=5.0 * 0.003, min_samples=10, eps=0.015)
        clust.fit(X)


def test_close_extract():
    # Test extract where extraction eps is close to scaled epsPrime

    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # Compute OPTICS
    clust = OPTICS(max_eps=1.0, cluster_method='dbscan',
                   eps=0.3, min_samples=10)
    # check warning when centers are passed
    assert_warns(RuntimeWarning, clust.fit, X)
    # Cluster ordering starts at 0; max cluster label = 2 is 3 clusters
    assert_equal(max(clust.labels_), 2)


@pytest.mark.parametrize('eps', [0.1, .3, .5])
@pytest.mark.parametrize('min_samples', [3, 10, 20])
def test_dbscan_optics_parity(eps, min_samples):
    # Test that OPTICS clustering labels are <= 5% difference of DBSCAN

    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # calculate optics with dbscan extract at 0.3 epsilon
    op = OPTICS(min_samples=min_samples, cluster_method='dbscan',
                eps=eps).fit(X)

    # calculate dbscan labels
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(X)

    contingency = contingency_matrix(db.labels_, op.labels_)
    agree = min(np.sum(np.max(contingency, axis=0)),
                np.sum(np.max(contingency, axis=1)))
    disagree = X.shape[0] - agree

    percent_mismatch = np.round((disagree - 1) / X.shape[0], 2)

    # verify label mismatch is <= 5% labels
    assert percent_mismatch <= 0.05


# try arbitrary minimum sizes
@pytest.mark.parametrize('min_cluster_size', range(2, X.shape[0] // 10, 23))
def test_min_cluster_size(min_cluster_size):
    redX = X[::2]  # reduce for speed
    clust = OPTICS(min_samples=9, min_cluster_size=min_cluster_size).fit(redX)
    cluster_sizes = np.bincount(clust.labels_[clust.labels_ != -1])
    if cluster_sizes.size:
        assert min(cluster_sizes) >= min_cluster_size
    # check behaviour is the same when min_cluster_size is a fraction
    clust_frac = OPTICS(min_samples=9,
                        min_cluster_size=min_cluster_size / redX.shape[0])
    clust_frac.fit(redX)
    assert_array_equal(clust.labels_, clust_frac.labels_)


@pytest.mark.parametrize('min_cluster_size', [0, -1, 1.1, 2.2])
def test_min_cluster_size_invalid(min_cluster_size):
    clust = OPTICS(min_cluster_size=min_cluster_size)
    with pytest.raises(ValueError, match="must be a positive integer or a "):
        clust.fit(X)


def test_min_cluster_size_invalid2():
    clust = OPTICS(min_cluster_size=len(X) + 1)
    with pytest.raises(ValueError, match="must be no greater than the "):
        clust.fit(X)


def test_processing_order():
    # Ensure that we consider all unprocessed points,
    # not only direct neighbors. when picking the next point.
    Y = [[0], [10], [-10], [25]]
    clust = OPTICS(min_samples=3, max_eps=15).fit(Y)
    assert_array_equal(clust.reachability_, [np.inf, 10, 10, 15])
    assert_array_equal(clust.core_distances_, [10, 15, np.inf, np.inf])
    assert_array_equal(clust.ordering_, [0, 1, 2, 3])


def test_compare_to_ELKI():
    # Expected values, computed with (future) ELKI 0.7.5 using:
    # java -jar elki.jar cli -dbc.in csv -dbc.filter FixedDBIDsFilter
    #   -algorithm clustering.optics.OPTICSHeap -optics.minpts 5
    # where the FixedDBIDsFilter gives 0-indexed ids.
    r1 = [np.inf, 1.0574896366427478, 0.7587934993548423, 0.7290174038973836,
          0.7290174038973836, 0.7290174038973836, 0.6861627576116127,
          0.7587934993548423, 0.9280118450166668, 1.1748022534146194,
          3.3355455741292257, 0.49618389254482587, 0.2552805046961355,
          0.2552805046961355, 0.24944622248445714, 0.24944622248445714,
          0.24944622248445714, 0.2552805046961355, 0.2552805046961355,
          0.3086779122185853, 4.163024452756142, 1.623152630340929,
          0.45315840475822655, 0.25468325192031926, 0.2254004358159971,
          0.18765711877083036, 0.1821471333893275, 0.1821471333893275,
          0.18765711877083036, 0.18765711877083036, 0.2240202988740153,
          1.154337614548715, 1.342604473837069, 1.323308536402633,
          0.8607514948648837, 0.27219111215810565, 0.13260875220533205,
          0.13260875220533205, 0.09890587675958984, 0.09890587675958984,
          0.13548790801634494, 0.1575483940837384, 0.17515137170530226,
          0.17575920159442388, 0.27219111215810565, 0.6101447895405373,
          1.3189208094864302, 1.323308536402633, 2.2509184159764577,
          2.4517810628594527, 3.675977064404973, 3.8264795626020365,
          2.9130735341510614, 2.9130735341510614, 2.9130735341510614,
          2.9130735341510614, 2.8459300127258036, 2.8459300127258036,
          2.8459300127258036, 3.0321982337972537]
    o1 = [0, 3, 6, 4, 7, 8, 2, 9, 5, 1, 31, 30, 32, 34, 33, 38, 39, 35, 37, 36,
          44, 21, 23, 24, 22, 25, 27, 29, 26, 28, 20, 40, 45, 46, 10, 15, 11,
          13, 17, 19, 18, 12, 16, 14, 47, 49, 43, 48, 42, 41, 53, 57, 51, 52,
          56, 59, 54, 55, 58, 50]
    p1 = [-1, 0, 3, 6, 6, 6, 8, 3, 7, 5, 1, 31, 30, 30, 34, 34, 34, 32, 32, 37,
          36, 44, 21, 23, 24, 22, 25, 25, 22, 22, 22, 21, 40, 45, 46, 10, 15,
          15, 13, 13, 15, 11, 19, 15, 10, 47, 12, 45, 14, 43, 42, 53, 57, 57,
          57, 57, 59, 59, 59, 58]

    # Tests against known extraction array
    # Does NOT work with metric='euclidean', because sklearn euclidean has
    # worse numeric precision. 'minkowski' is slower but more accurate.
    clust1 = OPTICS(min_samples=5).fit(X)

    assert_array_equal(clust1.ordering_, np.array(o1))
    assert_array_equal(clust1.predecessor_[clust1.ordering_], np.array(p1))
    assert_allclose(clust1.reachability_[clust1.ordering_], np.array(r1))
    # ELKI currently does not print the core distances (which are not used much
    # in literature, but we can at least ensure to have this consistency:
    for i in clust1.ordering_[1:]:
        assert (clust1.reachability_[i] >=
                clust1.core_distances_[clust1.predecessor_[i]])

    # Expected values, computed with (future) ELKI 0.7.5 using
    r2 = [np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf,
          np.inf, np.inf, np.inf, 0.27219111215810565, 0.13260875220533205,
          0.13260875220533205, 0.09890587675958984, 0.09890587675958984,
          0.13548790801634494, 0.1575483940837384, 0.17515137170530226,
          0.17575920159442388, 0.27219111215810565, 0.4928068613197889,
          np.inf, 0.2666183922512113, 0.18765711877083036, 0.1821471333893275,
          0.1821471333893275, 0.1821471333893275, 0.18715928772277457,
          0.18765711877083036, 0.18765711877083036, 0.25468325192031926,
          np.inf, 0.2552805046961355, 0.2552805046961355, 0.24944622248445714,
          0.24944622248445714, 0.24944622248445714, 0.2552805046961355,
          0.2552805046961355, 0.3086779122185853, 0.34466409325984865,
          np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf,
          np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf,
          np.inf, np.inf]
    o2 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 11, 13, 17, 19, 18, 12, 16, 14,
          47, 46, 20, 22, 25, 23, 27, 29, 24, 26, 28, 21, 30, 32, 34, 33, 38,
          39, 35, 37, 36, 31, 40, 41, 42, 43, 44, 45, 48, 49, 50, 51, 52, 53,
          54, 55, 56, 57, 58, 59]
    p2 = [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 10, 15, 15, 13, 13, 15,
          11, 19, 15, 10, 47, -1, 20, 22, 25, 25, 25, 25, 22, 22, 23, -1, 30,
          30, 34, 34, 34, 32, 32, 37, 38, -1, -1, -1, -1, -1, -1, -1, -1, -1,
          -1, -1, -1, -1, -1, -1, -1, -1, -1]
    clust2 = OPTICS(min_samples=5, max_eps=0.5).fit(X)

    assert_array_equal(clust2.ordering_, np.array(o2))
    assert_array_equal(clust2.predecessor_[clust2.ordering_], np.array(p2))
    assert_allclose(clust2.reachability_[clust2.ordering_], np.array(r2))

    index = np.where(clust1.core_distances_ <= 0.5)[0]
    assert_allclose(clust1.core_distances_[index],
                    clust2.core_distances_[index])


def test_wrong_cluster_method():
    clust = OPTICS(cluster_method='superfancy')
    with pytest.raises(ValueError, match="cluster_method should be one of "):
        clust.fit(X)


def test_extract_dbscan():
    # testing an easy dbscan case. Not including clusters with different
    # densities.
    rng = np.random.RandomState(0)
    n_points_per_cluster = 20
    C1 = [-5, -2] + .2 * rng.randn(n_points_per_cluster, 2)
    C2 = [4, -1] + .2 * rng.randn(n_points_per_cluster, 2)
    C3 = [1, 2] + .2 * rng.randn(n_points_per_cluster, 2)
    C4 = [-2, 3] + .2 * rng.randn(n_points_per_cluster, 2)
    X = np.vstack((C1, C2, C3, C4))

    clust = OPTICS(cluster_method='dbscan', eps=.5).fit(X)
    assert_array_equal(np.sort(np.unique(clust.labels_)), [0, 1, 2, 3])


def test_precomputed_dists():
    redX = X[::2]
    dists = pairwise_distances(redX, metric='euclidean')
    clust1 = OPTICS(min_samples=10, algorithm='brute',
                    metric='precomputed').fit(dists)
    clust2 = OPTICS(min_samples=10, algorithm='brute',
                    metric='euclidean').fit(redX)

    assert_allclose(clust1.reachability_, clust2.reachability_)
    assert_array_equal(clust1.labels_, clust2.labels_)

def test_extract_xi():
    # small and easy test (no clusters around other clusters)
    # but with a clear noise data.
    rng = np.random.RandomState(0)
    n_points_per_cluster = 5

    C1 = [-5, -2] + .8 * rng.randn(n_points_per_cluster, 2)
    C2 = [4, -1] + .1 * rng.randn(n_points_per_cluster, 2)
    C3 = [1, -2] + .2 * rng.randn(n_points_per_cluster, 2)
    C4 = [-2, 3] + .3 * rng.randn(n_points_per_cluster, 2)
    C5 = [3, -2] + .6 * rng.randn(n_points_per_cluster, 2)
    C6 = [5, 6] + .2 * rng.randn(n_points_per_cluster, 2)
    X = np.vstack((C1, C2, C3, C4, C5, np.array([[100, 100]]), C6))

    clust = OPTICS(min_samples=3, min_cluster_size=2,
                   max_eps=np.inf, cluster_method='xi',
                   xi=0.05).fit(X)
    expected_labels = np.r_[[0] * 5, [3] * 5, [2] * 5, [1] * 5, [2] * 5,
                            -1, [4] * 5]
    assert_array_equal(clust.labels_, expected_labels)
