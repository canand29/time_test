# Licensing Information:  You are free to use or extend this codebase for
# educational purposes provided that (1) you do not distribute or publish
# solutions, (2) you retain this notice, and (3) inform Guni Sharon at 
# guni@tamu.edu regarding your usage (relevant statistics is reported to NSF).
# The development of this assignment was supported by NSF (IIS-2238979).
# Contributors:
# The core code base was developed by Guni Sharon (guni@tamu.edu).

from collections import defaultdict, OrderedDict
import numpy as np
from numpy.core.fromnumeric import argmax
from sympy.physics.units import action
from sympy.stats.rv import probability

from Solvers.Abstract_Solver import AbstractSolver
from lib import plotting


class MonteCarlo(AbstractSolver):
    def __init__(self, env, eval_env, options):
        assert str(env.observation_space).startswith("Discrete") or str(
            env.observation_space
        ).startswith("Tuple(Discrete"), (
            str(self) + " cannot handle non-discrete state spaces"
        )
        assert str(env.action_space).startswith("Discrete") or str(
            env.action_space
        ).startswith("Tuple(Discrete"), (
            str(self) + " cannot handle non-discrete action spaces"
        )
        super().__init__(env, eval_env, options)
        self.policy = self.make_epsilon_greedy_policy()

        # The final action-value function.
        # A nested dictionary that maps state -> (action -> action-value).
        self.Q = defaultdict(lambda: np.zeros(env.action_space.n))
        # Keeps track of sum and count of returns for each state
        # to calculate an average. We could use an array to save all
        # returns (like in the book) but that's memory inefficient.
        self.returns_sum = defaultdict(float)
        self.returns_count = defaultdict(float)

    def train_episode(self):
        """
        Run a single episode for (first visit) Monte Carlo Control using Epsilon-Greedy policies.

        Use:
            self.options.env: OpenAI gym environment.
            self.options.steps: steps per episode
            probs = self.policy(state): soft policy for a given state
            np.random.choice(np.arange(len(probs)), p=probs): random index
                from the given distribution 'probs'
            self.options.gamma: Gamma discount factor.
            next_state, reward, done, _ = self.step(action): advance one step in the environment

        Note:
            train_episode is called multiple times from run.py. Within
            train_episode you need to store the transitions in 1 complete
            trajectory/episode. Then using the transitions in that episode,
            update the Q-function. Set Q-values as the (simple) average return for 
            visited states over all sampled episodes
        """

        # Generate an episode.
        # An episode is an array of (state, action, reward) tuples
        episode = []
        state, _ = self.env.reset()
        discount_factor = self.options.gamma
        ################################
        #   YOUR IMPLEMENTATION HERE   #
        ################################
        done = False
        while not done:
            probs = self.policy(state)
            curr_action = np.random.choice(np.arange(len(probs)), p=probs)

            next_state, reward, done, _ = self.step(curr_action)
            episode.append((state, curr_action, reward))

            # print(f'{done} and {type(done)}')

            state = next_state
            # print(state)

            check_sa = set()
            for i, (s,a,_) in enumerate(episode):
                if (s,a) not in check_sa:
                    check_sa.add((s,a))
                    G = 0
                    for j in range(i, len(episode)):
                        _, _, reward = episode[j]
                        G += reward * (discount_factor ** (j-i))

                    self.returns_sum[(s, a)] += G
                    # print(self.returns_sum[(s, a)])
                    self.returns_count[(s, a)] += 1

                    self.Q[s][a] = self.returns_sum[(s, a)] / self.returns_count[(s, a)]


    def __str__(self):
        return "Monte Carlo"

    def make_epsilon_greedy_policy(self):
        """
        Creates an epsilon-greedy policy based on a given Q-estimates and epsilon.

        Use:
            self.Q: A dictionary that maps from state -> action-values.
                Each value is a numpy array of length nA
            self.options.epsilon: Chance the sample a random action. Float betwen 0 and 1.
            self.env.action_space.n: Number of actions in the environment.

        Returns:
            A function that takes the observation as an argument and returns
            the probabilities for each action in the form of a numpy array of length nA.

        """
        nA = self.env.action_space.n

        def policy_fn(observation):
            ################################
            #   YOUR IMPLEMENTATION HERE   #
            ################################
            q = self.Q[observation]
            best_action = np.argmax(q)
            action_probs = np.ones(nA) * self.options.epsilon / nA
            action_probs[best_action] = 1 - self.options.epsilon + (self.options.epsilon / nA)
            # print(action_probs)
            return action_probs
        return policy_fn

    def create_greedy_policy(self):
        """
        Creates a greedy (soft) policy based on Q values.

        Returns:
            A function that takes an observation as input and returns a greedy
            action

        Use:
            np.argmax(self.Q[state]): action with highest q value
        """

        def policy_fn(state):
            ################################
            #   YOUR IMPLEMENTATION HERE   #
            ################################
            # print(np.argmax(self.Q[state]))
            return np.argmax(self.Q[state])


        return policy_fn

    def plot(self, stats, smoothing_window, final=False):
        # For plotting: Create value function from action-value function
        # by picking the best action at each state
        V = defaultdict(float)
        for state, actions in self.Q.items():
            action_value = np.max(actions)
            V[state] = action_value
        plotting.plot_value_function(V, title="Final Value Function")


class OffPolicyMC(MonteCarlo):
    def __init__(self, env, eval_env, options):
        assert str(env.action_space).startswith("Discrete") or str(
            env.action_space
        ).startswith("Tuple(Discrete"), (
            str(self) + " cannot handle non-discrete action spaces"
        )
        super().__init__(env, eval_env, options)

        # The cumulative denominator of the weighted importance sampling formula
        # (across all episodes)
        self.C = defaultdict(lambda: np.zeros(env.action_space.n))

        # Our greedily policy we want to learn about
        self.target_policy = self.create_greedy_policy()
        # Our behavior policy we want to learn from
        self.behavior_policy = self.create_random_policy()

    def train_episode(self):
        """
        Run a single episode of Monte Carlo Control Off-Policy Control using Weighted Importance Sampling.

        Use:
            elf.env: OpenAI environment.
            self.options.steps: steps per episode
            self.behavior_policy(state): returns a soft policy which is the
                behavior policy (act according to this policy)
            episode.append((state, action, reward)): memorize a transition
            self.options.gamma: Gamma discount factor.
            new_state, reward, done, _ = self.step(action): To advance one step in the environment
            self.C[state][action]: weighted importance sampling formula denominator
            self.Q[state][action]: q value for ('state', 'action')
        """
        episode = []
        # Reset the environment
        state, _ = self.env.reset()
        discount_factor = self.options.gamma
        ################################
        #   YOUR IMPLEMENTATION HERE   #
        ################################
        done = False

        while not done:
            b = self.behavior_policy(state)
            curr_action = np.random.choice(np.arange(len(b)), p=b)
            next_state, reward, done, _ = self.step(curr_action)
            episode.append((state, curr_action, reward))
            state = next_state

        G = 0
        W = 1

        for i in range(len(episode)-1, -1, -1):
            state, action, reward = episode[i]
            G = discount_factor * G + reward

            self.C[state][action] +=  W
            self.Q[state][action] += (W/self.C[state][action]) * (G - self.Q[state][action])

            best_action = self.target_policy(state)

            if action != best_action:
                break
            W /= self.behavior_policy(state)[action]

        self.target_policy = self.create_greedy_policy()


    def create_random_policy(self):
        """
        Creates a random policy function.

        Use:
            self.env.action_space.n: Number of actions in the environment.

        Returns:
            A function that takes an observation as input and returns a vector
            of action probabilities
        """
        nA = self.env.action_space.n
        A = np.ones(nA, dtype=float) / nA

        def policy_fn(observation):
            return A

        return policy_fn

    def __str__(self):
        return "MC+IS"