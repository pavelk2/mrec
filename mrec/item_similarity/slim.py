"""
Train a Sparse Linear Methods (SLIM) item similarity model using various
methods for sparse regression.

See:
    Efficient Top-N Recommendation by Linear Regression,
    M. Levy and K. Jack, LSRS workshop at RecSys 2013.

    SLIM: Sparse linear methods for top-n recommender systems,
    X. Ning and G. Karypis, ICDM 2011.
    http://glaros.dtc.umn.edu/gkhome/fetch/papers/SLIM2011icdm.pdf
"""

from sklearn.linear_model import SGDRegressor, ElasticNet
from sklearn.preprocessing import binarize
import numpy as np

from recommender import ItemSimilarityRecommender

class NNFeatureSelectingSGDRegressor(object):
    """
    Wraps nearest-neighbour feature selection and regression in a single model.
    """

    def __init__(self,model,k):
        self.model = model
        self.k = k

    def fit(self,A,a):
        # find k-NN by brute force
        d = A.T.dot(a).flatten()  # distance = dot product
        nn = d.argsort()[-1:-1-self.k:-1]
        # fit the model to selected features only
        self.model.fit(A[:,nn],a)
        # set our weights for the selected "features" i.e. items
        self.coef_ = np.zeros(A.shape[1])
        self.coef_[nn] = self.model.coef_

    def __str__(self):
        return 'NN-feature selecting {0}'.format(self.model)

class SLIM(ItemSimilarityRecommender):
    """
    Parameters
    ==========

    l1_reg : float
        L1 regularisation constant.
    l2_reg : float
        L2 regularisation constant.
    fit_intercept : bool
        Whether to fit a constant term.
    ignore_negative_weights : bool
        If true discard any computed negative similarity weights.
    num_selected_features : int
        The number of "features" (i.e. most similar items) to retain when using feature selection.
    model : string
        The underlying model to use: sgd, elasticnet, fs_sgd.
        :sgd: SGDRegressor with elasticnet penalty
        :elasticnet: ElasticNet
        :fs_sgd: NNFeatureSelectingSGDRegressor
    """
    def __init__(self,
                 l1_reg=0.01,
                 l2_reg=0.001,
                 fit_intercept=False,
                 ignore_negative_weights=False,
                 num_selected_features=200,
                 model='sgd'):
        alpha = l1_reg+l2_reg
        l1_ratio = l1_reg/alpha
        if model == 'sgd':
            self.model = SGDRegressor(penalty='elasticnet',fit_intercept=fit_intercept,alpha=alpha,l1_ratio=l1_ratio)
        elif model == 'elasticnet':
            self.model = ElasticNet(alpha=alpha,l1_ratio=l1_ratio,positive=True,fit_intercept=fit_intercept,copy_X=False)
        elif model == 'fs_sgd':
            m = SGDRegressor(penalty='elasticnet',fit_intercept=fit_intercept,alpha=alpha,l1_ratio=l1_ratio)
            self.model = NNFeatureSelectingSGDRegressor(m,num_selected_features)
        else:
            raise SystemExit('unknown model type: {0}'.format(model))
        self.ignore_negative_weights = ignore_negative_weights

    def compute_similarities(self,j):
        """Compute item similarity weights for item j."""
        A = self.dataset
        # zero out the j-th column of A so we get w[j] = 0
        a = A.fast_get_col(j)
        A.fast_update_col(j,np.zeros(a.nnz))
        self.model.fit(A.X,a.toarray())
        # reinstate the j-th column of A
        A.fast_update_col(j,a.data)
        w = self.model.coef_
        if self.ignore_negative_weights:
            w[w<0] = 0
        return w

    def compute_similarities_from_vec(self,a):
        """Compute item similarity weights for out-of-dataset item vector."""
        self.model.fit(self.dataset.X,a)
        return self.model.coef_

    def __str__(self):
        if self.ignore_negative_weights:
            return 'SLIM({0} ignoring negative weights)'.format(self.model)
        else:
            return 'SLIM({0})'.format(self.model)

if __name__ == '__main__':

    # use SLIM like this:

    import random
    import StringIO
    from mrec import load_fast_sparse_matrix

    random.seed(0)

    print 'loading test data...'
    data = """\
%%MatrixMarket matrix coordinate real general
3 5 9
1	1	1
1	2	1
1	3	1
1	4	1
2	2	1
2	3	1
2	5	1
3	3	1
3	4	1
"""
    print data
    dataset = load_fast_sparse_matrix('mm',StringIO.StringIO(data))
    num_users,num_items = dataset.shape

    model = SLIM()

    num_samples = 2

    def output(i,j,val):
        # convert back to 1-indexed
        print '{0}\t{1}\t{2:.3f}'.format(i+1,j+1,val)

    print 'computing some item similarities...'
    print 'item\tsim\tweight'
    # if we want we can compute these individually without calling train()
    model.init(dataset)
    for i in random.sample(xrange(num_items),num_samples):
        for j,weight in model.get_similar_items(i,max_similar_items=10):
            output(i,j,weight)

    print 'learning entire similarity matrix...'
    model.train(dataset)
    print 'making some recommendations...'
    print 'user\trec\tscore'
    for u in random.sample(xrange(num_users),num_samples):
        for i,score in model.recommend_items(u,max_items=10):
            output(u,i,score)

    print 'making batch recommendations...'
    recs = model.batch_recommend_items()
    for u in xrange(num_users):
        for i,score in recs[u]:
            output(u,i,score)

    print 'making range recommendations...'
    for start,end in [(0,2),(2,3)]:
        recs = model.range_recommend_items(start,end)
        for u in xrange(start,end):
            for i,score in recs[u-start]:
                output(u,i,score)