import numpy as np
import tensorflow as tf
from . import embedding, transformer, final
from static import constants, _math

class Model(tf.Module):
    def __init__(self):
        super(Model, self).__init__()
        self.embed = embedding.Layer(constants.d_model,
            name = "nova_embedding_layer")
        tfmrs = {}
        for i in range (1, constants.nova_tfmr + 1):
            tfmrs = {
                **tfmrs,
                **{i: transformer.Layer(constants.d_model,
                    constants.num_heads , constants.dff)}
                }
        self.tfmrs = tfmrs
        self.final = final.Layer(len(constants.vocabulary), constants.d_model)
        return

    def embedPass(self, in_batch):
        # embedding tokenized batch
        big_stack = []
        for seq in in_batch:
            small_stack = tf.stack([self.embed(tkn) for tkn in seq])
            big_stack.append(small_stack)

        # stacking all batches into the embedding batch
        return tf.stack(big_stack)

    def transformPass(self, embed_batch):
        fpass_batch = embed_batch
        for tfmr in self.tfmrs.values():
            fpass_batch = tfmr(fpass_batch)
        return fpass_batch

    def fPass(self, in_batch, training = False):
        #embed token batch
        embed_batch = self.embedPass(in_batch)

        # pass through transformer layers
        tfmr_batch = self.transformPass(embed_batch)

        # pass through last layer for probabilities and refiting
        out_batch = self.final(tfmr_batch)

        # evaluate output batch (using armax, which may not be the best)
        logits = tf.argmax(out_batch[:,-1,:], axis = -1)

        return logits

    @property
    def Trainables(self):
        trainables = self.embed.Trainables
        for tfmr in self.tfmrs.values():
            trainables += tfmr.Trainables
        trainables += self.final.Trainables
        return trainables
