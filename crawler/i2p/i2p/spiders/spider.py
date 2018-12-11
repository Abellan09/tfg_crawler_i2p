# encoding: utf-8

import scrapy		# https://doc.scrapy.org/en/latest
import shutil		# https://docs.python.org/2/library/shutil.html
import urlparse		# https://docs.python.org/2/library/urlparse.html
import time			# https://docs.python.org/2/library/time.html
import json			# https://docs.python.org/2/library/json.html
import nltk			# https://www.nltk.org
from i2p.items import I2PItem, I2PItemFinal, LanguageItem
from py_translator import Translator
from scrapy.linkextractors import LinkExtractor
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError 
from twisted.internet.error import TimeoutError, TCPTimedOutError

class I2P_Spider(scrapy.Spider):
	
	'''
	EN: Spider that is responsible for extracting the links contained in an eepsite.
	SP: Spider que se encarga de extraer los links contenidos en un eepsite.
	
	For general information about scrapy.Spider, see: https://doc.scrapy.org/en/latest/topics/spiders.html
	Para obtener información general sobre scrapy.Spider, consulte: https://doc.scrapy.org/en/latest/topics/spiders.html
	'''
	
	name = "i2p"
	end_time = 0
	start_time = 0
	start_urls = []
	visited_links = []
	parse_eepsite = None
	error = True
	itemLang = LanguageItem()
	itemLang["language"] = []
	LANGUAGES_NLTK = [] # Lista de idiomas disponibles en la nltk
	LANGUAGES_GOOGLE = {} # Lista de idiomas disponibles en API Google
	main_page = True
	aux = I2PItem()
	item = I2PItemFinal()
	item["extracted_eepsites"]=[]
	extractor_i2p = LinkExtractor(tags=('a','area','base','link','audio','embed','iframe','img','input','script','source','track','video'),attrs=('href','src','srcset'),allow_domains=('i2p'),deny_extensions=())
	
	def __init__(self, url=None, *args, **kwargs):
		'''
		EN: It initializes the seed URL list with the URL that has been passed as a parameter
		SP: Inicializa la lista de URLs semilla con la URL pasada como parámetro.
		
		:param url: url of the site to crawl / url del site a crawlear
		'''
		super(I2P_Spider, self).__init__(*args, **kwargs)
		self.logger.debug("Dentro de __init__()")
		if url is not None:
			self.start_urls.append(url)
			self.parse_eepsite = urlparse.urlparse(url)
			with open("i2p/spiders/data/languages_google.json") as f:
				self.LANGUAGES_GOOGLE = json.load(f)
			with open("i2p/spiders/data/languages_nltk.txt") as g:
				line = g.readline()
				while line != "":
					line = line.replace("\n", "")
					self.LANGUAGES_NLTK.append(line)
					line = g.readline()
			self.start_time = time.time()
			self.logger.info("Start URL: %s", self.parse_eepsite)
		else:
			self.logger.error("No URL passed to crawl")
	
	def start_requests(self):
		'''
		EN: It returns an iterable of Requests which the Spider will begin to crawl.
		SP: Devuelve un iterable de Requests que el Spider comenzará a crawlear.
		'''
		self.logger.debug("Dentro de start_requests()")
		for u in self.start_urls:
			yield scrapy.Request(u, callback = self.parse, errback = self.err, dont_filter=True)  
	
	def detect_language_nltk(self, sample):
		'''
		EN: It uses NLTK platform to detect the language of a given sample.
		SP: Utiliza la plataforma NLTK para detectar el idioma de una muestra dada.
		
		:param sample: sample of text from which the language is detected / muestra de texto a partir de la cual detectar el idioma
		:return: the detected language / el idioma detectado
		'''
		# Dividimos el texto de entrada en tokens o palabras únicas
		tokens = nltk.tokenize.word_tokenize(sample)
		tokens = [t.strip().lower() for t in tokens] # Convierte todos los textos a minúsculas para su posterior comparación
		# Creamos un dict donde almacenaremos la cuenta de las stopwords para cada idioma
		lang_count = {}
		# Por cada idioma
		try:
			for lang in self.LANGUAGES_NLTK:
				# Obtenemos las stopwords del idioma del módulo nltk
				stop_words = unicode(nltk.corpus.stopwords.words(lang))
				lang_count[lang] = 0 # Inicializa a 0 el contador para cada idioma
				# Recorremos las palabras del texto a analizar
				for word in tokens:
					if word in stop_words: # Si la palabra se encuentra entre las stopwords, incrementa el contador
						lang_count[lang] += 1
			#print lang_count
			# Obtenemos el idioma con el número mayor de coincidencias
			language_nltk = max(lang_count, key=lang_count.get)
			if lang_count[language_nltk] == 0:
				language_nltk = 'undefined'
		except UnicodeDecodeError as e:
			print 'Error'
			language_nltk = 'error'
		finally:
			return language_nltk
	
	def detect_language_google(self, sample):
		'''
		EN: It uses Google Translate to detect the language of a given sample.
		SP: Utiliza el Traductor de Google para detectar el idioma de una muestra dada.
		
		:param sample: sample of text from which the language is detected / muestra de texto a partir de la cual detectar el idioma
		:return: the detected language / el idioma detectado
		'''
		translator = Translator()
		det = translator.detect(sample)
		language_google = self.LANGUAGES_GOOGLE[det.lang]
		return language_google

	def detect_language(self, response):
		'''
		EN: It detects the language of the main page.
		SP: Detecta el idioma de la página principal.
		
		:param response: response returned by an eepsite main page / respuesta devuelta por la página principal de un eepsite.
		'''
		source_url = urlparse.urlparse(response.url)
		self.itemLang["eepsite"] = source_url.netloc
		title = response.xpath('normalize-space(//title/text())').extract()
		self.itemLang["title"] = title
		paragraphs = response.xpath('normalize-space(//p)').extract()
		h1 = response.xpath('//h1/text()').extract()
		h2 = response.xpath('//h2/text()').extract()
		h3 = response.xpath('//h3/text()').extract()
		h4 = response.xpath('//h4/text()').extract()
		sample = title + paragraphs + h1 + h2 + h3 + h4
		sample = ' '.join(sample)
		if len(sample)>500:
			sample = sample[0:500]
		self.itemLang["sample"] = sample
		# Con API de GOOGLE:
		language_google=self.detect_language_google(sample)
		# Con nltk:
		language_nltk=self.detect_language_nltk(sample)
		self.itemLang["language"].append(language_google)
		self.itemLang["language"].append(language_nltk)

	def parse(self, response):
		'''
		EN: It handles the downloaded response for each of the made requests.
		SP: Maneja la respuesta descargada para cada una de las solicitudes realizadas.
				
		It stores the extracted eepsites from each response in the corresponding Item.
		In addition, it makes a yield to itself with a Request for each of the internal links of the site (with what the whole site is crawled).
		Almacena en el Item correspondiente los eepsites extraídos de cada response.
		Además, hace un yield a sí mismo con una Request para cada uno de los enlaces internos del site (con lo que se crawlea el site entero).
		
		:param response: response returned by an eepsite / respuesta devuelta por un eepsite.
		'''
		self.logger.debug("Dentro de parse()")
		self.error = False
		self.logger.info("Recieved response from {}".format(response.url))
		if(self.main_page):
			self.detect_language(response)
			self.main_page=False
		self.visited_links.append(response.url)
		self.aux["source_url"] = response.url
		source_url = urlparse.urlparse(response.url)
		self.aux["source_site"] = source_url.netloc
		links = self.get_links(response)
		urls_list = []
		for link in links:
			urls_list.append(link.url)
			parse_link = urlparse.urlparse(link.url)
			if (parse_link.netloc not in self.item["extracted_eepsites"]) and (parse_link.netloc != self.parse_eepsite.netloc):
				self.item["extracted_eepsites"].append(parse_link.netloc)
			if (link.url not in self.visited_links) and (self.parse_eepsite.netloc == parse_link.netloc):
				self.visited_links.append(link.url)
				yield scrapy.Request (link.url, callback = self.parse, errback = self.err, dont_filter=True)
		self.aux["list_of_urls"] = urls_list
		self.end_time = time.time()
		self.itemLang["time"] = str(self.end_time - self.start_time)
		yield self.aux
		yield self.item
		yield self.itemLang
	
	def get_links(self, response):
		'''
		EN: It extracts the links from a certain eepsite.
		SP: Extrae los links de un determinado eepsite.
		
		:param response: response returned by an eepsite / respuesta devuelta por un eepsite
		:return: list that contains the extracted links / lista que contiene los links extraídos
		'''
		self.logger.debug("Dentro de get_links()")
		links = self.extractor_i2p.extract_links(response)
		return links
	
	def closed (self, reason):
		'''
		EN: It is called when the spider has ended the crawling process.
		SP: Se llama cuando el spider ha terminado todo el proceso de crawling.
		
		It generates an empty file with ".fail" extension in case there has been any error and the site 
		hasn't been crawled correctly; otherwise, it generates an empty file with ".ok" extension.
		Genera un archivo vacío con extensión ".fail" en caso de que haya habido algún error y el site no 
		se haya podido crawlear correctamente; en caso contrario, genera un archivo vacío con extensión ".ok".
		
		:param reason: a string which describes the reason why the spider was closed / string que describre por qué ha finalizado el spider
		'''
		self.logger.debug("Dentro de closed()")
		self.logger.info("SPIDER FINALIZADO")
		self.logger.info("ERROR = " + str(self.error))
		site = self.parse_eepsite.netloc
		ok = "./i2p/spiders/finished/" + site + ".ok"
		fail = "./i2p/spiders/finished/" + site + ".fail"
		if self.error:
			f = open(fail, "w")
			f.close()
			self.logger.info(site + ".fail has been created at /i2p/spiders/finished")
		else:
			f = open(ok, "w")
			f.close()
			self.logger.info(site + ".ok has been created at /i2p/spiders/finished")
			self.logger.info("Total time taken in crawling " + self.parse_eepsite.netloc + ": " + str(self.end_time - self.start_time) + " seconds.")
		
	def err(self, failure):
		'''
		EN: It reports about possible errors that may occur when a request fails.
		SP: Reporta los posibles errores que pueden producirse cuando una petición falla.
		
		This function is called when an error occurs (if any exception was raised while processing
		the request). The showed errors are: HttpError, DNSLookupError y TimeoutError.
		Esta función es llamada cuando ocurre un error (si se lanza cualquier extensión mientras se	procesa
		una respuesta). Son mostrados los errores: HttpError, DNSLookupError y TimeoutError.
		
		:param failure: type of error which has ocurred / tipo de error que ha ocurrido (https://twistedmatrix.com/documents/current/api/twisted.python.failure.Failure.html)
		'''
		self.logger.debug("Dentro de err()")
		#self.error = True
		self.logger.error(repr(failure))  
		if failure.check(HttpError):
			response = failure.value.response 
			self.logger.error("HttpError occurred on %s", response.url)  
		elif failure.check(DNSLookupError): 
			request = failure.request 
			self.logger.error("DNSLookupError occurred on %s", request.url) 
		elif failure.check(TimeoutError, TCPTimedOutError): 
			request = failure.request 
			self.logger.error("TimeoutError occurred on %s", request.url) 
