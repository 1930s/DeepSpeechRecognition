import os
import tensorflow as tf
import numpy as np
from keras import backend as K

# 定义解码器------------------------------------
def decode_ctc(num_result, num2word):
	result = num_result[:, :, :]
	in_len = np.zeros((1), dtype = np.int32)
	in_len[0] = result.shape[1]
	r = K.ctc_decode(result, in_len, greedy = True, beam_width=10, top_paths=1)
	r1 = K.get_value(r[0][0])
	r1 = r1[0]
	text = []
	for i in r1:
		text.append(num2word[i])
	return r1, text


# 0.准备解码所需字典，参数需和训练一致，也可以将字典保存到本地，直接进行读取
from utils import get_data, data_hparams
data_args = data_hparams()
data_args.data_type = 'train'
data_args.data_path = 'data/'
data_args.thchs30 = True
data_args.aishell = False
data_args.prime = False
data_args.stcmd = False
data_args.batch_size = 1
data_args.data_length = 10
data_args.shuffle = True
train_data = get_data(data_args)


# 1.声学模型-----------------------------------
from model_speech.cnn_ctc import Am, am_hparams

am_args = am_hparams()
am_args.vocab_size = len(train_data.am_vocab)
am_args.is_training = False
am = Am(am_args)
print('loading acoustic model...')
am.model.load_weights('logs_am/model.h5', by_name=True)

# 2.语言模型-------------------------------------------
from model_language.transformer import Lm, lm_hparams

lm_args = lm_hparams()
lm_args.input_vocab_size = len(train_data.pny_vocab)
lm_args.label_vocab_size = len(train_data.han_vocab)
print('loading language model...')
lm = Lm(lm_args)
sess = tf.Session(graph=lm.graph)
with lm.graph.as_default():
    saver =tf.train.Saver()
with sess.as_default():
    latest = tf.train.latest_checkpoint('logs_lm')
    saver.restore(sess, latest)

# 3. 准备测试所需数据， 不必和训练数据一致，通过设置data_args.data_type测试，
#    此处应设为'test'，我用了'train'因为演示模型较小，如果使用'test'看不出效果，
#    且会出现未出现的词。
data_args.data_type = 'train'
data_args.shuffle = False
data_args.batch_size = 1
test_data = get_data(data_args)

am_batch = test_data.get_am_batch()

for i in range(10):
    print('\n the ', i, 'th example.')
    # 载入训练好的模型，并进行识别
    inputs, _ = next(am_batch)
    x = inputs['the_inputs']
    y = test_data.pny_lst[i]
    result = am.model.predict(x, steps=1)
    # 将数字结果转化为文本结果
    _, text = decode_ctc(result, train_data.am_vocab)
    text = ' '.join(text)
    print('文本结果：', text)
    print('原文结果：', ' '.join(y))
    with sess.as_default():
        text = text.strip('\n').split(' ')
        x = np.array([train_data.pny_vocab.index(pny) for pny in text])
        x = x.reshape(1, -1)
        preds = sess.run(lm.preds, {lm.x: x})
        got = ''.join(train_data.han_vocab[idx] for idx in preds[0])
        print('原文汉字：', test_data.han_lst[i])
        print('识别结果：', got)
sess.close()
