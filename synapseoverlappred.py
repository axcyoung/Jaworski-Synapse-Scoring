from PIL import Image
from sklearn.model_selection import train_test_split
from matplotlib import pyplot as plt

import os, math, random
import tensorflow as tf
print('Tensorflow version ' + tf.__version__)
import numpy as np
import ImageGenerator_3D as generator

#Epochs
EPOCHS = 5
TRAIN_SPLIT = 0.75
total_loss_list = []
accuracy_list = []

class Model(tf.keras.Model):
    def __init__(self):
        """
        CNN Architecture for Synapse Overlap Prediction
        """
        super(Model, self).__init__()

        self.batch_size = 128
        self.num_classes_BCE = 1
        self.num_classes_CCE = 4
        self.loss_list = []
        self.learning_rate = .01
        self.alpha = 0.0 #gradient masking constant
        #self.dropout_rate = .3
        #self.var_ep = .000001

        self.layer1 = tf.keras.layers.Conv2D(filters=32, kernel_size=3, activation='relu')
        self.layer2 = tf.keras.layers.Conv2D(filters=64, kernel_size=3, activation='relu')
        self.layer3 = tf.keras.layers.Conv2D(filters=128, kernel_size=6, activation='relu')
        self.layer4 = tf.keras.layers.Flatten()
        #dense_sig 1-class for classifying synapse-nonsynapse, dense_soft 4-class for overlap scoring
        self.dense_sig = tf.keras.layers.Dense(self.num_classes_BCE, activation='sigmoid')
        self.dense_soft = tf.keras.layers.Dense(self.num_classes_CCE, activation='softmax')
        
    #def lr_decay(epoch):
    #    self.learning_rate = 0.01 * math.pow(0.6, epoch)

    def call(self, inputs):
        """
        Runs a forward pass on an input batch of images.
        :param inputs: images, shape (batch_size, 39[z], 10[y], 10[x], 1[channels])
        :return: probs: shape (batch_size, 4[num_classes])
        """
        #print(np.shape(inputs))
        layer1Output = self.layer1(inputs)
        layer2Output = self.layer2(layer1Output)
        layer3Output = self.layer3(layer2Output)
        layer4Output = self.layer4(layer3Output)
        probs_s = self.dense_sig(layer4Output)
        probs_i = self.dense_soft(layer4Output)
        #print(probs_s[0:5])
        #return (probs_s, probs_i)
        return probs_s

    def loss(self, probs_s, probs_i, labels_s, labels_i):
        """
        Calculates the binary cross-entropy loss after one forward pass.
        :param probs: shape (batch_size, 4)
        :param labels: shape (batch_size, 4)
        :return: loss
        """ 
        L_s = tf.keras.losses.binary_crossentropy(labels_s, probs_s) #comment out all L_i, labels_i
        L_i = tf.keras.losses.categorical_crossentropy(labels_i, probs_i)
        return tf.reduce_mean(L_s + L_i*labels_s*self.alpha)
        
    def accuracy(self, probs_s, probs_i, labels_s, labels_i, s_indices):
        """
        Calculates the model's prediction accuracy by comparing
        probs to correct labels
        :param probs: shape (batch_size, 4)
        :param labels: shape (batch_size, 4)
        :return: accuracy
        """
        probs_s = tf.reshape(probs_s, (-1))
        #print(probs_s[0:10])
        #print(tf.round(probs_s[0:10]))
        #print(labels_s[0:10])
        #print(tf.equal(tf.round(probs_s[0:10]), labels_s[0:10]))
        s_correct = tf.equal(tf.round(probs_s), labels_s)
        print('Synapse-nonsynapse accuracy: ' + str(tf.reduce_mean(tf.cast(s_correct, tf.float32))))
        accuracy_list.append(tf.reduce_mean(tf.cast(s_correct, tf.float32)))
        #probs_i = tf.gather(probs_i, s_indices)
        #labels_i = tf.gather(labels_i, s_indices)
        #print('Confusion matrix: ' + str(tf.math.confusion_matrix(tf.argmax(labels_i, 1), tf.argmax(probs_i, 1))))


def train(model, X_s_train, y_s_train, y_i_train):
    '''
    Trains the model on all of the inputs and labels for one epoch. Inputs are batched.
    :param model: the initialized model to use for the forward pass and backward pass
    :param train_inputs: train inputs shape (batch_size, 39[z], 10[y], 10[x], 1[channels])
    :param train_labels: train labels (all labels to use for training), 
    shape (num_labels, num_classes)
    :return: Optionally list of losses per batch to use for visualize_loss
    '''
    num_examples = y_s_train.shape[0]
    shuffle_indices = np.arange(0, num_examples)
    shuffle_indices = tf.random.shuffle(shuffle_indices)
    X_s_train = tf.gather(X_s_train, shuffle_indices)
    y_s_train = tf.gather(y_s_train, shuffle_indices)
    y_i_train = tf.gather(y_i_train, shuffle_indices)

    optimizer = tf.keras.optimizers.Adam(model.learning_rate)

    for i in range(0, num_examples, model.batch_size):
        X_s_batch = X_s_train[i:i + model.batch_size]
        y_s_batch = y_s_train[i:i + model.batch_size]
        y_i_batch = y_i_train[i:i + model.batch_size]   
        
        with tf.GradientTape() as tape:
            probs_s, probs_i = model.call(X_s_batch)
            #print(np.shape(probs_s))
            #print(np.shape(probs_i))
            #print(np.shape(y_i_batch))
            loss = model.loss(probs_s, probs_i, y_s_batch, y_i_batch)
            #gradient masking?

        gradients = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        total_loss_list.append(loss)
        

def test(model, X_s_test, y_s_test, y_i_test, s_indices):
    """
    Tests the model on the test inputs and labels.
    :param model: the initialized model to use for the forward pass and backward pass
    :param test_inputs: test inputs shape (batch_size, 39[z], 10[y], 10[x], 1[channels])
    :param test_labels: test labels (all labels to use for testing), 
    shape (num_labels, num_classes)
    :return: test accuracy - average accuracy across all batches
    """
    
    #probs_s, probs_i = model.call(X_s_test)
    probs_s = model.call(X_s_test)
    model.accuracy(probs_s, [], y_s_test, y_i_test, s_indices)
    """
    accuracies = []
    for i in range(0, y_s_test.shape[0], model.batch_size):
        X_s_batch = X_s_test[i:i + model.batch_size]
        y_s_batch = y_s_test[i:i + model.batch_size]
        y_i_batch = y_i_test[i:i + model.batch_size]
        
        probs = model.call(X_s_batch)
        model.accuracy(probs, label_batch)
    """
    

def visualize(losses): 
    """
    Uses Matplotlib to visualize the losses of our model.
    :param losses: list of loss data stored from train. Can use the model's loss_list 
    field 
    """
    x = [i for i in range(len(losses))]
    plt.plot(x, losses)
    plt.title('Loss per batch')
    plt.xlabel('Batch')
    plt.ylabel('Loss')
    plt.show()  


def visualize_results(predicted_labels, true_labels):
    """
    Uses Matplotlib to visualize synapse overlap label accuracy.
    :param predicted_labels
    :param true_labels
    """
    plt.scatter(predicted_labels, true_labels, s=70, alpha=.03)
    plt.title('Predicted v True')
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.show()


def main():
    s_input = np.load('data.npy') #max pixel values, shape (n, 39, 10, 10, 1)
    s_input = tf.convert_to_tensor(s_input, dtype=tf.float32)
    s_labels = np.load('synapse_nonsynapse.npy') #synapse-nonsynapse labels, shape (n)
    s_labels = tf.convert_to_tensor(s_labels, dtype=tf.float32)
    i_labels = np.load('labels.npy') #one-hot overlap labels padded to correct size, shape (n, 4)
    i_labels = tf.convert_to_tensor(i_labels, dtype=tf.float32)
    print('synapse_nonsynapse_input: ' + str(np.shape(s_input)))
    print('synapse_nonsynapse_labels: ' + str(np.shape(s_labels)))
    print('overlap_labels: ' + str(np.shape(i_labels)))
    
    #Split training and testing, maybe use sklearn train_test_split
    num_examples = s_labels.shape[0]
    shuffle_indices = np.arange(0, num_examples)
    shuffle_indices = tf.random.shuffle(shuffle_indices)
    s_input = tf.gather(s_input, shuffle_indices)
    s_labels = tf.gather(s_labels, shuffle_indices)
    i_labels = tf.gather(i_labels, shuffle_indices)
    
    split_index = int(num_examples*TRAIN_SPLIT)
    X_s_train = s_input[0:split_index]
    y_s_train = s_labels[0:split_index]
    y_i_train = i_labels[0:split_index]
    X_s_test = s_input[split_index:num_examples]
    y_s_test = s_labels[split_index:num_examples]
    y_i_test = i_labels[split_index:num_examples]
    
    #For properly removing padding for overlap score accuracy
    #shuffle_indices = shuffle_indices[split_index:num_examples]
    #s_indices = []
    #for i in range(shuffle_indices.shape[0]):
    #    if shuffle_indices[i] <= 191:
    #        s_indices.append(i)
    # s_indices = tf.convert_to_tensor(s_indices)
    
    print("X_s_train shape: " + str(np.shape(X_s_train)))
    print("y_s_train shape: " + str(np.shape(y_s_train)))
    
    m = Model()
    m.compile(optimizer=tf.keras.optimizers.Adam(lr=0.01),
                  loss='binary_crossentropy',
                  metrics=['accuracy'])
    history = m.fit(x=X_s_train, y=y_s_train, steps_per_epoch=len(X_s_train) / 32, epochs=EPOCHS,
                    validation_data=(X_s_test, y_s_test))
    #for i in range(EPOCHS):
    #    train(m, X_s_train, y_s_train, y_i_train)
    #    test(m, X_s_test, y_s_test, y_i_test, [])
        #m.lr_decay(i)
        
    test(m, X_s_train, y_s_train, y_i_train, [])
    #test(m, X_s_test, y_s_test, y_i_test, s_indices)
    visualize(total_loss_list)
    visualize(accuracy_list)
    #print(total_loss_list[len(total_loss_list)-10:len(total_loss_list)])
    return

if __name__ == '__main__':
    main()
