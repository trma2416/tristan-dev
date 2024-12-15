import tensorflow as tf
from . import masking

class Layer(tf.Module):
    def __init__(self, embed_dim, num_heads, kernel_transformation=None, name=None):
        super(Layer, self).__init__(name=name)
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.kernel_transformation = kernel_transformation or self.default_kernel_transformation

        assert embed_dim % num_heads == 0, "Embedding dimension must be divisible by the number of heads."

        self.depth = embed_dim // num_heads

        # Initialize weights
        self.wq = tf.Variable(tf.random.normal([embed_dim, embed_dim]), name='wq')
        self.wk = tf.Variable(tf.random.normal([embed_dim, embed_dim]), name='wk')
        self.wv = tf.Variable(tf.random.normal([embed_dim, embed_dim]), name='wv')
        self.dense = tf.keras.layers.Dense(embed_dim)

        # layer normalization
        self.layernorm = tf.keras.layers.LayerNormalization(epsilon = 1e-6)

    def default_kernel_transformation(self, x):
        return tf.nn.relu(x) + 1e-6

    def split_heads(self, x, batch_size):
        """Split the last dimension into (num_heads, depth).
        Transpose the result to shape (batch_size, num_heads, seq_len, depth).
        """
        x = tf.reshape(x, (batch_size, -1, self.num_heads, self.depth))
        return tf.transpose(x, perm=[0, 2, 1, 3])

    def __call__(self, q, k, v, mask=None):
        batch_size = tf.shape(q)[0]
        seq_len = tf.shape(q)[1]

        # creating lookahead mask
        lookahead_mask = masking.create_look_ahead_mask(seq_len)

        #dotting q,k,v
        q = tf.tensordot(q, self.wq, axes=[[2], [0]])  # (batch_size, seq_len, embed_dim)
        k = tf.tensordot(k, self.wk, axes=[[2], [0]])  # (batch_size, seq_len, embed_dim)
        v = tf.tensordot(v, self.wv, axes=[[2], [0]])  # (batch_size, seq_len, embed_dim)

        # normalize layers
        q = self.layernorm(q)
        k = self.layernorm(k)
        v = self.layernorm(v)

        # split_heads
        q = self.split_heads(q, batch_size)  # (batch_size, num_heads, seq_len, depth)
        k = self.split_heads(k, batch_size)  # (batch_size, num_heads, seq_len, depth)
        v = self.split_heads(v, batch_size)  # (batch_size, num_heads, seq_len, depth)

        # Apply kernel transformation
        q_prime = self.kernel_transformation(q)  # Apply kernel transformation
        k_prime = self.kernel_transformation(k)

        # FAVOR+ Mechanism
        kv = tf.einsum('...nd,...ne->...de', k_prime, v)
        z = 1.0 / (tf.einsum('...nd,...d->...n', q_prime, tf.reduce_sum(k_prime, axis=-2)) + 1e-6)
        attention_output = tf.einsum('...nd,...de,...n->...ne', q_prime, kv, z)

        # apply mask
        attention_output = masking.masked_attention(q_prime, k_prime, v, lookahead_mask)

        attention_output = tf.reshape(attention_output, (batch_size, -1, self.embed_dim))
        output = self.dense(attention_output)

        #normalize outputs
        return self.layernorm(output)

    @property
    def Parameters(self):
        return [self.wq, self.wk, self.wv, self.layernorm.gamma, self.layernorm.beta]
