import numpy as np
from sklearn.decomposition import NMF
from collections import Counter
from scipy import sparse


class ParetoNMF(object):
    """
    This is a class that heuristically determines the number of latent topics
    in a corpus of documents iteratively, founded on the following assumptions:

    a) n percent of documents within a corpus is noise
    b) more topics extracted from the corpus using NMF if the rich contentrc/
    within a corpus, which makes up 1-n percent of the documents within a
    corpus, are the items being decomposed further into topics rather than
    the n percent of documents which is the noise
    c) if by adding another topic to the document, the number of topics under
    which the 1-n percent of documents fall under stay the same, then no more
    additional topics should be added
    d) while there are several topics within a document, a document is assigned
    to fall under a topic based on the topic under which its loading is
    highest along the W matrix
    """
    def __init__(self, noise_pct=.2, step=2, start=2, pnmf_verbose=False,
                 max_steps=100, init='nndsvdar', solver='cd',
                 tol=0.0001, max_iter=200, random_state=None,
                 alpha=0.0, l1_ratio=0.0, shuffle=False,
                 nls_max_iter=2000, sparseness=None, beta=1, eta=0.1,
                 verbose=0):
        """
        Args:
            the following are the parameters to tune the model:

            noise_pct (float): this is the percent of noise within
            the corpus. by default, this is set to .2, it can also be set to
            'auto' where during the evaluate step, paretonmf will check for
            the percentage of the unique corpus that contributes to 80
            percent of the content in the corpus
            (so as to follow the 80:20 pareto principle)
            there is also an auto setting on this where what IPNMF will
            do is to select the percentage of document that hold 80 percent
            of the content of all the tokens inside the matrix so that
            in that way, the 80:20 rule pertains to the content of the
            documents rather than making it a fast 80 percent of the
            total document count

            step (int): this is the size of the step between how many
            topics are extracted from NMF at a time, by default this is
            set to 2, but can be tuned to a larger number if it is
            estimated that there are many topics in the corpus
            there is also an auto setting for this where, for now,
            IPNMF will set the step size to be based on the bag of words
            length and the corpus length where auto is computed as
            the bag of words count divided by the corpus length

            start (int): this is the number of topics to be initially
            extracted from the corpus using NMF, this is initially set
            to 2 but can be tuned if it is estimated that there are
            many topics in the corpus

            pnmf_verbose (boolean): True to have the model give the
            status per iteration else false

            max_iter (int): this is the maximum number of iterations
            the model will make in determining the number of topics
            to extract

            ============================================================
            the rest below are the parameters to set for the NMF object
            taken from sklearn

            init :  'random' | 'nndsvd' |  'nndsvda' | 'nndsvdar'
            | 'custom'
            Method used to initialize the procedure.
            Default: 'nndsvdar' if n_components < n_features,
            otherwise random.
            Valid options:

            - 'random': non-negative random matrices, scaled with:
                sqrt(X.mean() / n_components)

            - 'nndsvd': Nonnegative Double Singular Value Decomposition
                (NNDSVD) initialization (better for sparseness)

            - 'nndsvda': NNDSVD with zeros filled with the average of X
                (better when sparsity is not desired)

            - 'nndsvdar': NNDSVD with zeros filled with small random
                values (generally faster, less accurate alternative
                to NNDSVDa for when sparsity is not desired)

            - 'custom': use custom matrices W and H

            solver : 'pg' | 'cd'
                Numerical solver to use:
                'pg' is a Projected Gradient solver (deprecated).
                'cd' is a Coordinate Descent solver (recommended).

                .. versionadded:: 0.17
                   Coordinate Descent solver.

                .. versionchanged:: 0.17
                   Deprecated Projected Gradient solver.

            tol : double, default: 1e-4
                Tolerance value used in stopping conditions.

            max_iter : integer, default: 200
                Number of iterations to compute.

            random_state : integer seed, RandomState instance,
                or None (default)
                Random number generator seed control.

            alpha : double, default: 0.
                Constant that multiplies the regularization terms.
                Set it to zero to have no regularization.

                .. versionadded:: 0.17
                   *alpha* used in the Coordinate Descent solver.

            l1_ratio : double, default: 0.
            The regularization mixing parameter, with
            0 <= l1_ratio <= 1.
            For l1_ratio = 0 the penalty is an elementwise L2 penalty
            (aka Frobenius Norm).
            For l1_ratio = 1 it is an elementwise L1 penalty.
            For 0 < l1_ratio < 1, the penalty is a combination of
            L1 and L2.

            .. versionadded:: 0.17
               Regularization parameter *l1_ratio* used in the
               Coordinate Descent solver.

            shuffle : boolean, default: False
                If true, randomize the order of coordinates in the CD solver.

                .. versionadded:: 0.17
                   *shuffle* parameter used in the Coordinate Descent solver.

            nls_max_iter : integer, default: 2000
                Number of iterations in NLS subproblem.
                Used only in the deprecated 'pg' solver.

            .. versionchanged:: 0.17
               Deprecated Projected Gradient solver.
               Use Coordinate Descent solver instead.

        sparseness : 'data' | 'components' | None, default: None
            Where to enforce sparsity in the model.
            Used only in the deprecated 'pg' solver.

            .. versionchanged:: 0.17
               Deprecated Projected Gradient solver.
               Use Coordinate Descent solver instead.

        beta : double, default: 1
            Degree of sparseness, if sparseness is not None. Larger values mean
            more sparseness. Used only in the deprecated 'pg' solver.

            .. versionchanged:: 0.17
               Deprecated Projected Gradient solver.
               Use Coordinate Descent solver instead.

        eta : double, default: 0.1
            Degree of correctness to maintain, if sparsity is not None. Smaller
            values mean larger error. Used only in the deprecated 'pg' solver.

            .. versionchanged:: 0.17
               Deprecated Projected Gradient solver.
               Use Coordinate Descent solver instead.
        """
        self.noise_pct = noise_pct
        self.step = step
        self.start = start
        self.pnmf_verbose = pnmf_verbose
        self.max_steps = max_steps
        self.init = init
        self.solver = solver
        self.tol = tol
        self.max_iter = max_iter
        self.random_state = random_state
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self.shuffle = shuffle
        self.nls_max_iter = nls_max_iter
        self.sparseness = sparseness
        self.beta = beta
        self.eta = eta
        self.rich_topics = 0
        self.verbose = verbose

    def evaluate(self, matrix):
        """
        Args:
            matrix (2d array): this is the matrix of documents and tokens
            where the number of topics needs to be determined, this has worked
            with compressed sparse row matrices before
        Returns
            topic_count (int): this is the number of topics that IPNMF was
            able to pick up heuristically
        """
        if self.noise_pct == 'auto':
            self._pareto_corpus_content(matrix, .8)
        if self.step == 'auto':
            self._determine_auto_step_size(matrix)
        if self.pnmf_verbose:
            print('initializing evaluation...')
        self.corpus_count = matrix.shape[0]
        self.rich_content = int(self.corpus_count * (1-self.noise_pct))
        self.noise_content = self.corpus_count - self.rich_content
        topic_array = np.arange(self.start, self.max_steps * self.step +
                                self.start, self.step)
        for topic_count in topic_array:
            if self.pnmf_verbose:
                print('extracting {} topics...'.format(topic_count))
            self.topic_count = topic_count
            nmf = NMF(n_components=self.topic_count, init=self.init,
                      solver=self.solver, tol=self.tol, max_iter=self.max_iter,
                      random_state=self.random_state, alpha=self.alpha,
                      l1_ratio=self.l1_ratio, verbose=self.verbose,
                      shuffle=self.shuffle, nls_max_iter=self.nls_max_iter,
                      sparseness=self.sparseness, beta=self.beta,
                      eta=self.eta)
            W = nmf.fit_transform(matrix)
            self.nmf = nmf
            self.topic_labels = np.apply_along_axis(func1d=np.argmax,
                                                    axis=1, arr=W)
            self.topic_summary = Counter(self.topic_labels)
            if self._stopping_condition():
                if self.pnmf_verbose:
                    print('heuristic topic count is {}'
                          .format(self.topic_count - self.step))
                self.topic_count = self.topic_count - self.step
                nmf = NMF(n_components=self.topic_count, init=self.init,
                          solver=self.solver, tol=self.tol,
                          max_iter=self.max_iter,
                          random_state=self.random_state, alpha=self.alpha,
                          l1_ratio=self.l1_ratio, verbose=self.verbose,
                          shuffle=self.shuffle,
                          nls_max_iter=self.nls_max_iter,
                          sparseness=self.sparseness, beta=self.beta,
                          eta=self.eta)
                nmf.fit(matrix)
                self.nmf = self.previous_nmf
                return self.topic_count
            else:
                self.previous_nmf = nmf

    def _stopping_condition(self):
        """
        Args:
            None
        Returns:
            boolean: True if the stopping condition has been met else False
        """
        sorted_topics = np.sort(np.array(self.topic_summary.values()))[::-1]
        cum_sum = np.cumsum(sorted_topics)
        if self.pnmf_verbose:
            print('{} is the topic distribution'.format(sorted_topics))
        topics_with_rich_content = np.sum(cum_sum < self.rich_content)
        string_rc = '{} is the current count of topics with rich content'
        string = 'there are {} topics within the bulk of the topic distributon'
        if self.pnmf_verbose:
            print(string_rc.format(self.rich_topics))
            print(string.format(topics_with_rich_content))
            print('\n')
        if topics_with_rich_content == self.rich_topics:
            return True
        else:
            self.rich_topics = topics_with_rich_content
            return False

    def _pareto_corpus_content(self, matrix, n_percent):
        """
        This private function computes for the percentage of the total
        corpus to consider for the "bulk" of the content by looking
        at what percentage of total documents holds n_percent, set to
        80 percent for now, holds 80 percent of the total token content.
        The inverse of this percentage is saved in self.noise_pct

        Args:
            matrix (2d array): this can be the csr matrix that has the
            tfidf or tf matrix information
            n_percent (float): this is a tunable value that is used as the cut
            off for determining the percentage of documents that holds this
            n information based on the distribution of documents and
            their tokens inside them
        Returns:
            None
        """
        sparse_matrix = sparse.csr_matrix(matrix)
        sparse_matrix = np.unique(sparse_matrix)[0]
        total_documents = sparse_matrix.shape[0]
        token_count = np.array(np.sum(sparse_matrix > 0, axis=1)).T[0]
        sorted_token_count = sorted(token_count, reverse=True)
        total_tokens = np.sum(token_count)
        majority_information = int(total_tokens * n_percent)
        majority_docs = \
            np.sum(np.cumsum(sorted_token_count) < majority_information)
        self.noise_pct = 1-float(majority_docs)/total_documents

    def _determine_auto_step_size(self, matrix):
        """
        This private function computes the auto step size to take when the
        setting for step size is auto. This saves the step size that
        heuristically can be considered given the shape of the matrix from
        which topics are extracted in the self.step attribute

        Args:
            matrix (2d array): matrix to have the topics extracted from
        Returns
            None
        """
        self.step = int(round(float(matrix.shape[1])/matrix.shape[0]))
        if self.step == 0:
            self.step = 1
