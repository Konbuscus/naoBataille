# -*- coding: utf-8 -*-
import image
from naoqi import ALProxy
from naoqi import ALBroker
from naoqi import ALModule
from random import random
import sys
import numpy as np
from optparse import OptionParser

sys.path.insert(0, "/usr/local/lib/python2.7/site-packages/")
import cv2
import time
from PIL import Image

""" usage 

nao_blackjack.py <training_image_filename> <training_labels_filename>
	nao_blackjack.py Training/train4.jpg Training/train4.tsv

"""

# Defining constants
# STAND, HIT, LOSE, WIN = 0, 1, 2, 3
WIN, LOSE, DRAW, WAITING = 1, 2, 3, 4
NAO_IP = "192.168.1.238"
NAO_PORT = 9559
NaoHighLow = None
memory = None


# TODO Wait for his turn (wait for head sensor touch)

# Main entry point
def main(training_image_filename="Training/essai.jpg", training_labels_filename="thomasCard.tst",
         num_training_cards=32):
    parser = OptionParser()
    parser.add_option("--pip",
                      help="Parent broker port. The IP address or your robot",
                      dest="pip")
    parser.add_option("--pport",
                      help="Parent broker port. The port NAOqi is listening to",
                      dest="pport",
                      type="int")
    parser.set_defaults(
        pip=NAO_IP,
        pport=9559)

    (opts, args_) = parser.parse_args()
    pip = opts.pip
    pport = opts.pport

    myBroker = ALBroker("myBroker",
                        "0.0.0.0",  # listen to anyone
                        0,  # find a free port and use it
                        pip,  # parent broker IP
                        pport)  # parent broker port

    global NaoBlackJack
    NaoBlackJack = NaoBlackJackModule("NaoBlackJack", training_image_filename, training_labels_filename,
                                      num_training_cards)

    try:
        while NaoBlackJack.playing:
            time.sleep(1)
        else:
            print
            print "Tured off by touching read tactile sensor"
            myBroker.shutdown()
    except KeyboardInterrupt:
        print
        print "Interrupted by user, shutting down"
        myBroker.shutdown()
        sys.exit(0)


class NaoBlackJackModule(ALModule):
    def __init__(self, name, training_image_filename, training_labels_filename, num_training_cards):
        ALModule.__init__(self, name)
        self.playing = True
        # No need for IP and port here because
        # we have our Python broker connected to NAOqi broker

        # Create a proxy to ALTextToSpeech for later use
        self.training = get_training(training_labels_filename, training_image_filename, num_training_cards, False)

        self.tts = ALProxy("ALTextToSpeech")
        self.initVideoClient()

        global memory

        # Subscribe to Front Tactile Sensor Event
        memory = ALProxy("ALMemory")
        # self.tts.say("Initialisation terminée, distribue les cartes et appuyer sur ma tête")
        memory.subscribeToEvent("FrontTactilTouched", "NaoBlackJack", "onFrontTouchDetected")
        memory.subscribeToEvent("RearTactilTouched", "NaoBlackJack", "onRearTouchDetected")

    def initVideoClient(self):
        self.camProxy = ALProxy("ALVideoDevice")
        resolution = 3  # qVGA
        colorSpace = 11  # RGB
        self.videoClient = self.camProxy.subscribe("python_client", resolution, colorSpace, 5)

    def getNaoImage(self):
        t0 = time.time()
        naoImage = self.camProxy.getImageRemote(self.videoClient)
        if naoImage == None :
            sys.exit()
        t1 = time.time()
        print "Image acquisition delay ", t1 - t0

        # Get the image arraySize and pixel array.
        imageWidth = naoImage[0]
        imageHeight = naoImage[1]
        array = naoImage[6]

        # Create a PIL Image from our pixel array.
        im = Image.frombytes("RGB", (imageWidth, imageHeight), array)

        # Create cv2 image using the PIL image
        cvImage = np.array(im)
        cvImage = cv2.cvtColor(cvImage, cv2.COLOR_RGB2BGR)
        return cvImage

    def unsubscribeVideoClient(self):
        self.camProxy = ALProxy("ALVideoDevice")
        self.camProxy.unsubscribe(self.videoClient)

    def speakDecision(self, decision):

        if decision == LOSE:
            rnd = random()
            if rnd < 0.1:
                self.tts.say("La bataille est perdue, mais la guerre ne fait que commencer")
            elif rnd < 0.4:
                self.tts.say("J'ai perdu cette partie, ne te réjouit pas fdp")
            elif rnd < 0.6:
                self.tts.say("J'ai perdu voilà mes derniers boulons")
            elif rnd < 0.7:
                self.tts.say("Je deteste perdre, je vas venir te tuer dans ton sommeil")
            else:
                self.tts.say("Je vais t'insulter, le sel est en moi")
        elif decision == WIN:
            rnd = random()
            if rnd < 0.3:
                self.tts.say("Essaye de perdre du poids, au lieu de perdre à la bataille")
            elif rnd < 0.4:
                self.tts.say("Tu as encore perdu, depuis quand es-tu devenu si faible")
            elif rnd < 0.5:
                self.tts.say("Alors on continue de perdre ? Essaye d'utiliser la force la prochaine fois")
            elif rnd < 0.6:
                self.tts.say("Essaye de te faire mousser la moustache, il paraît que ça porte chance")
            elif rnd < 0.7:
                self.tts.say("Tu aimes perdres ? Les simplexes sont fait pour toi.")
            else:
                self.tts.say("Au lieu d'acheter un paquet de carte, achète un pack EPSI")

    # This will be called when Nao front tactile sensor is touched.
    def onFrontTouchDetected(self, *_args):
        # Unsubscribe so it doest get fired again while playing
        memory.unsubscribeToEvent("FrontTactilTouched", "NaoBlackJack")
        self.tts.say("C'est l'heure du DUEL !")
        # Setting variables for the round

        decision = 0
        prev_naoNumCards = 0
        prev_dealerNumCards = 0

        while decision == 0:  # or decision==HIT or decision==STAND:
            # Vue de nao (image)
            im = self.getNaoImage()
            height, width, depth = im.shape
            naoCardsImg = im[height / 2:height, 0:width]
            naoNumCards = getCountCards(naoCardsImg, 0.8)
            print "Counted", naoNumCards, "naoCards on the image"

            dealerCardsImg = im[0:height / 2, 0:width]
            dealerNumCards = getCountCards(dealerCardsImg, 0.8)
            print "Counted", dealerNumCards, "dealerCards on the image"
            # If Nao does't have the required number of cards he will tell you
            # if decision!=STAND #and (naoNumCards <= prev_naoNumCards or naoNumCards < 2 or naoNumCards > prev_naoNumCards+2):
            print(decision)
            if decision != DRAW:

                # Compare les deux cartes
                # Récupérer carte de nao
                # Récupérer carte du dealer / joueur
                # change la décision en fonction du gagant

                if decision == WIN:

                    # Phrases random comme plus bas
                    self.tts.say("BRAVO TU TE CROIS DRÔLE ON RECOMMENCE !")
                    time.sleep(3)
                    continue

                elif decision == LOSE:
                    self.tts.say("AHAH T MOVAI JACK")
                    time.sleep(3)
                    continue

            else:
                self.tts.say("A L'ATTAQUE ENCULER, BALANCE TA CARTE")
                time.sleep(3)
                continue

            # if dealerNumCards < 1 or dealerNumCards > prev_dealerNumCards + 2:
            # 	self.tts.say("Please deal card to yourslef")
            # 	time.sleep(3)
            # 	continue

            # Debug: uncomment to see registered images
            # for i,c in enumerate(getCards(im,naoNumCards+dealerNumCards)):
            # 	card = find_closest_card(training,c,)
            # 	cv2.imshow(str(card) + " " + str(i),c)
            # cv2.waitKey(0)

            # If Nao has called STAND, his cards are the same and there is no need for new card recognition
            # Recuperation des cartes
            # if decision!=STAND:
            # 	naoCards = [find_closest_card(self.training, c) for c in getCards(naoCardsImg, naoNumCards)]
            # print "Regognized following naoCards:", naoCards, "=", sum_cards(naoCards)
            # dealerCards = [find_closest_card(self.training, c) for c in getCards(dealerCardsImg, dealerNumCards)]
            # print "Regognized following dealerCards:", dealerCards, "=", sum_cards(dealerCards)

            prev_decision = decision
            dealerCards = [find_closest_card(self.training, c) for c in getCards(dealerCardsImg, dealerNumCards)]
            naoCards = [find_closest_card(self.training, c) for c in getCards(naoCardsImg, naoNumCards)]
            decision = decide(naoCards, dealerCards)

            print "Previous decision was", prev_decision, "my new decision is", decision
            # if prev_decision==STAND and decision==HIT:
            # 	decision=STAND
            # if decision!=STAND or decision!=prev_decision:
            # 	self.speakDecision(decision)
            self.speakDecision(decision)

            prev_naoNumCards = naoNumCards
            prev_dealerNumCards = dealerNumCards
            time.sleep(3)

        self.tts.say("Si vous voulez rejouer, donnez les cartes et appuyer sur ma tête")

        # Subscribe again to the event
        memory.subscribeToEvent("FrontTactilTouched", "NaoBlackJack", "onFrontTouchDetected")

    def onRearTouchDetected(self, *_args):
        memory.unsubscribeToEvent("RearTactilTouched", "NaoBlackJack")
        self.tts.say("It was nice playing with you. Have a good day")
        memory.unsubscribeToEvent("FrontTactilTouched", "NaoBlackJack")
        self.unsubscribeVideoClient()
        self.playing = False


###############################################################################
# Image Processing
###############################################################################
def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 2)
    thresh, o = cv2.threshold(blur, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)  # .adaptiveThreshold(blur,255,1,1,5,1)
    return o


def imgdiff(img1, img2):
    img1 = cv2.GaussianBlur(img1, (5, 5), 5)
    img2 = cv2.GaussianBlur(img2, (5, 5), 5)
    diff = cv2.absdiff(img1, img2)
    diff = cv2.GaussianBlur(diff, (5, 5), 5)
    flag, diff = cv2.threshold(diff, 200, 255, cv2.THRESH_BINARY)
    return np.sum(diff)


def find_closest_card(training, img):
    features = preprocess(img)
    return sorted(training.values(), key=lambda x: imgdiff(x[1], features))[0][0]


def rectify(h):
    try:
        h = h.reshape((4, 2))
    except:
        # print "Failed to rectify card"
        return False
    hnew = np.zeros((4, 2), dtype=np.float32)

    add = h.sum(1)
    hnew[0] = h[np.argmin(add)]
    hnew[2] = h[np.argmax(add)]

    diff = np.diff(h, axis=1)
    hnew[1] = h[np.argmin(diff)]
    hnew[3] = h[np.argmax(diff)]

    return hnew


###############################################################################
# Card Extraction
###############################################################################  
def getCards(im, numcards=4):
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (1, 1), 1000)
    flag, thresh = cv2.threshold(blur, 120, 255, cv2.THRESH_BINARY)
    # Manque image (pas sûr)
    image, contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:numcards]

    # Debug: Uncomment to see how the countours of the cards detected
    # cv2.drawContours(im, contours, -1, (0,255,0), 3)
    # newWidth = 1024
    # newHeigh = im.shape[0] / (im.shape[1]/newWidth)
    # imx = cv2.resize(im,(newWidth,newHeigh))
    # cv2.imshow("getCards", imx)
    # cv2.waitKey(0)

    for card in contours:
        peri = cv2.arcLength(card, True)
        poly = cv2.approxPolyDP(card, 0.02 * peri, True)
        approx = rectify(poly)

        if type(approx) != bool:
            h = np.array([[0, 0], [449, 0], [449, 449], [0, 449]], np.float32)
            transform = cv2.getPerspectiveTransform(approx, h)
            warp = cv2.warpPerspective(im, transform, (450, 450))

            yield warp


def getCountCards(im, cardDiference=0.8):
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (1, 1), 1000)
    flag, thresh = cv2.threshold(blur, 120, 255, cv2.THRESH_BINARY)
    image, contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    prev = 0
    count = 0
    curr = 0.0
    for i, card in enumerate(contours):
        peri = cv2.arcLength(card, True)
        poly = cv2.approxPolyDP(card, 0.02 * peri, True)
        approx = rectify(poly)

        # Check if the countours are rectifiable
        if type(approx) == bool:
            # If they are not, countinue, probably it is not a card
            continue
        curr = cv2.contourArea(card)

        # Check if the card has similar size to the previous card
        if (prev * cardDiference) <= curr:
            count += 1
            prev = curr
        else:
            break
    return count


def get_training(training_labels_filename, training_image_filename, num_training_cards, human_assisted_training=False):
    training = {}
    labels = {}

    if (human_assisted_training):
        train_labels_file = open(training_labels_filename, "w+")
    else:
        for line in file(training_labels_filename):
            key, num, suit = line.strip().split()
            labels[int(key)] = num
    print "Training"

    im = cv2.imread(training_image_filename)
    for i, c in enumerate(getCards(im, num_training_cards)):
        if human_assisted_training:
            pcard = preprocess(c)
            cv2.imshow("Preprocessed Card", pcard)
            cv2.waitKey(0)
            human_input = raw_input("Enter the value of the card in format NUM <tab> SUIT: ")
            train_labels_file.write(str(i) + "\t" + human_input.upper() + "\n")
        else:
            training[i] = (labels[i], preprocess(c))

    print "Done training"
    return training


###############################################################################
# Power functions
###############################################################################  
def card_value(card, result):
    if card == '1' or card == 'A':
        return 14  # Ace value
    # if card=='K' or card=='Q' or card=='J' or card=='10':
    elif card == 'K':
        return 13
    elif card == 'Q':
        return 12
    elif card == 'J':
        return 11
    else:
        return int(card)


# def sum_cards(nao_cards):
# 	result=0
# 	aces = 0
# 	for card in nao_cards:
# 		if card=='A':
# 			aces+=1
# 		result+=card_value(card, result)
# 		while result>21 and aces>0:
# 			result-=10
# 			aces-=1
# 	return result

def decide(nao_cards, dealer_cards):
    # Première carte du tableau des deux mains
    result = 0
    resultDealer = card_value(dealer_cards, result)
    resultNao = card_value(nao_cards, result)
    realNaoCard = resultNao
    print resultNao
    print resultDealer
    realPlayerCard = resultDealer
    if realPlayerCard > realNaoCard:
        return WIN

    elif realPlayerCard < realNaoCard:
        return LOSE

    elif realNaoCard == realPlayerCard:
        return DRAW


# nao_sum = sum_cards(nao_cards)
# dealer_sum = sum_cards(dealer_cards)
# if nao_sum==21 or dealer_sum > 21 or (dealer_sum>=17 and 21-dealer_sum >= 21-nao_sum):
# 	return WIN
# elif nao_sum>21 or (dealer_sum>=17 and 21-dealer_sum < 21-nao_sum):
# 	return LOSE
# elif nao_sum<=11:
# 	return HIT
# elif nao_sum==12 and 4 > dealer_sum > 6:
# 	return HIT
# elif 13 <= nao_sum <= 16 and dealer_sum > 6:
# 	return HIT
# else:
# 	return STAND

def speakDecision(decision):
    if decision == LOSE:
        tts.say("BORDEL JAI PERDU")
    elif decision == WIN:
        tts.say("JAI GAGNER")


camProxy = None

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print "Using", sys.argv[0], "with default training image 'train4.jpg' and default training set 'train4.tsv'"
        main()
    else:
        main(sys.argv[1], sys.argv[2], 32)
