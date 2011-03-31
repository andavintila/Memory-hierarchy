from threading import *
from asc_t1_defs import *

#bariera reentranta
bariera = Semaphore(value=0)
bariera2 = Semaphore(value=0)
regcritica = Semaphore(value=1)
threads = 1 
n = threads
last_step = 0

def barrier3():
	global bariera, bariera2, regcritica, n, n2, threads
	regcritica.acquire()
	n -= 1
	if n == 0:
		for i in range(threads):
			bariera.release()
		n2 = threads
	regcritica.release()
 
	bariera.acquire()
 
	regcritica.acquire()
	n2 -= 1
	if n2 == 0:
		for i in range(threads):
			bariera2.release()
		n = threads
	regcritica.release()
 
	bariera2.acquire()


def wait_for_next_time_step(object, done):
	#este apelata de system manager la sf fiecarui pas de timp;
	#param done = 1 - pasul de timp curent a fost ultimul
	#done = 0 - altfel
	#param object va fi chiar obiectul SystemManager
	#threadul SystemManager-ului trebuie sa astepte in aceasta functie pana cand threadurile coresp celorlalte entit au ajuns la finalul pasului de timp curent
	#apoi se apeleaza increase_time_step a obiectului system_manager 
	global last_step, threads;
	
	barrier3();
	last_step = done;
	object.increase_time_step();

	barrier3();
	

class RAM(GenericRAM):
	def __init__(self, system_manager, num_ram_cells, num_ram_requests_per_time_step):
		GenericRAM.__init__(self)
		self.__system_manager = system_manager;
		self.nram = num_ram_cells;
		self.max_requests = num_ram_requests_per_time_step;
		self.cell_dict = {}; #dictionar in care se retin valorile adreselor celulelor
		self.last_req = {}; #dictionar cu care se inregistreaza cererile de la pasul anterior
		self.new_req = {}; #dictionar cu care se inregistreaza cererile de la pasul curent
		self.current_req = 0;
		self.count = 0;
		self.aux_req = {}; #dictionar auxiliar pentru retinerea in last_req numai a max_requests la un pas

	def set_cell_value(self, addr, value):
		#seteaza valoarea celulei cu nr addr, sau echivalent de la adresa addr, din RAM la valoarea value
		if len(self.cell_dict.keys()) < self.nram:
			self.cell_dict[addr] = value;

	def run(self):
		global last_step;
		self.__system_manager.register_ram(self);
		while last_step != 1:
			if len(self.last_req.keys()) > 0:
				for i in self.last_req:
					for j in self.last_req[i]:
						j[1].receive_ans_ram(j[2], self.cell_dict[j[2]]); #trimite raspunsul catre cacheul i
						self.__system_manager.ram_notify_submit_answer(j[1], j[0], j[2]);
			barrier3();
			self.count = 0;
			self.last_req.clear();
			for i in self.new_req.keys():
				if self.count < self.max_requests:
					self.last_req[i] = self.new_req[i];
					self.count += 1;
				else:
					self.aux_req[i] = self.new_req[i]; 
			
			self.new_req.clear();
			self.new_req = self.aux_req.copy();
			self.aux_req.clear();
			barrier3();	
			
		
	def receive_req_cache(self, cache, rid, addr):
		self.new_req[self.current_req] = [];
		self.new_req[self.current_req].append([rid, cache, addr]); #id + cache + addr
		self.current_req += 1;

class Cache(GenericCache):
	def __init__(self, num_cache_cells, ram, system_manager):
		GenericCache.__init__(self)
		self.__system_manager = system_manager;
		self.ncache = num_cache_cells;
		self.__ram = ram;
		self.cell_dict = {}; #addresa - pozitie, valoare
		self.last_req = {}; #cereri de la regset
		self.new_req = {};
		self.last_ans = {}; #raspunsuri de la ram
		self.new_ans = {};
		self.reqid = 0;
		self.pozitie = 0;
		self.aux_poz = 0;
		self.requests_pending = {} #adresa - reg set, reqid
		self.aux_addr = 0;

	def set_cell_value(self, addr, value):
		if len(self.cell_dict.keys()) < self.ncache:
			self.cell_dict[addr] = [self.pozitie, value];
			self.pozitie += 1;
		else:
			for i in self.cell_dict:
				if self.cell_dict[i][0] == self.aux_poz:
					self.aux_addr = i;
					break;
			del self.cell_dict[self.aux_addr]
			self.cell_dict[addr] = [self.aux_poz, value];
			self.aux_poz +=1;
			if self.aux_poz == self.ncache:
				self.aux_poz = 0;
					
	def run(self):
		global last_step;
		self.__system_manager.register_cache(self);
		while last_step != 1:
			#proceseaza raspunsuri primite de la ram pasii anteriori
			if len(self.last_ans.keys()) > 0:
				for i in self.last_ans:
					if not i in self.cell_dict:
						self.set_cell_value(i, self.last_ans[i]);
						self.__system_manager.cache_notify_store_value(self.cell_dict[i][0], i);
						#cache_notify_store_value(position, addr)
					if i in self.requests_pending:
						for j in self.requests_pending[i]:
							j[0].receive_ans_cache(i, self.cell_dict[i][1]);
							self.__system_manager.cache_notify_submit_answer(j[0], j[1], i);
						del self.requests_pending[i];
				
			
			#proceseaza cereri primite de la set reg pasii anteriori
			if len(self.last_req.keys()) > 0:
				for i in self.last_req: #rid
					for j in self.last_req[i]:
						if j[1] in self.cell_dict:
							j[0].receive_ans_cache(j[1], self.cell_dict[j[1]][1]); #trimite raspunsul catre reg_set_ul j[0]
							self.__system_manager.cache_notify_submit_answer(j[0], i, j[1]);
						else:
							if not j[1] in self.requests_pending:
								self.requests_pending[j[1]] = []
							self.__ram.receive_req_cache(self, self.reqid, j[1]); #trimite cerere catre ram
							self.__system_manager.cache_notify_submit_request(self.reqid, j[1]);
							self.requests_pending[j[1]].append([j[0], i]) 
							self.reqid += 1; 
			barrier3();
			self.last_ans = self.new_ans.copy();
			self.new_ans = {};
			self.last_req = self.new_req.copy();
			self.new_req = {};
			barrier3();

	def receive_ans_ram(self, addr, value): #primeste raspunsuri de la ram
		self.new_ans[addr] = value;

	def receive_req_regset(self, regset, rid, addr): #primeste cereri de la reg set
		if not rid in self.new_req:
			self.new_req[rid] = []; 
		self.new_req[rid].append([regset, addr]);

	

class RegSet(GenericRegisterSet):
	def __init__(self, num_register_cells, cache, system_manager):
		GenericRegisterSet.__init__(self);
		self.nreg = num_register_cells;
		self.__system_manager = system_manager;
		self.__cache = cache;
		self.cell_dict = {}; #addresa - pozitie, valoare
		self.last_req = {}; #cereri de la procesor
		self.new_req = {};
		self.last_ans = {}; #raspunsuri de la cache
		self.new_ans = {};
		self.reqid = 0;
		self.pozitie = 0;
		self.aux_poz = 0;
		self.aux_addr = 0;
		self.requests_pending = {}; #adresa - procesor, reqid

	def set_cell_value(self, addr, value):
		if len(self.cell_dict.keys()) < self.nreg:
			self.cell_dict[addr] = [self.pozitie, value];
			self.pozitie += 1;
		else:
			for i in self.cell_dict:
				if self.cell_dict[i][0] == self.aux_poz:
					self.aux_addr = i;
					break;
			del self.cell_dict[self.aux_addr];
			self.cell_dict[addr] = [self.aux_poz , value];
			self.aux_poz += 1;
			if self.aux_poz == self.nreg:
				self.aux_poz = 0;
	def run(self):
		global last_step;
		self.__system_manager.register_register_set(self)
		while last_step != 1:
			#proceseaza raspunsuri primite de la cache pasii anteriori
			if len(self.last_ans.keys()) > 0:
				for i in self.last_ans:
					if not i in self.cell_dict:
						
						self.set_cell_value(i, self.last_ans[i]);
						self.__system_manager.register_set_notify_store_value(self.cell_dict[i][0], i);
					if i in self.requests_pending:
						self.__system_manager.register_set_notify_submit_answer(self.requests_pending[i][0], self.requests_pending[i][1], i);
						self.requests_pending[i][0].receive_ans_regset(i, self.cell_dict[i][1]);
						
						del self.requests_pending[i];
			#proceseaza cereri primite de la procesor pasii anteriori
			if len(self.last_req.keys()) > 0:
				for i in self.last_req: #rid
					if self.last_req[i][1] in self.cell_dict:
						self.__system_manager.register_set_notify_submit_answer(self.last_req[i][0], i, self.last_req[i][1]);
						self.last_req[i][0].receive_ans_regset(self.last_req[i][1], self.cell_dict[self.last_req[i][1]][1]); #trimite raspunsul catre procesorul i
						
					elif not self.last_req[i][1] in self.requests_pending:
						self.__cache.receive_req_regset(self, self.reqid, self.last_req[i][1]); #trimite cerere catre cache
						self.__system_manager.register_set_notify_submit_request(self.__cache, self.reqid, self.last_req[i][1]);
						self.requests_pending[self.last_req[i][1]] = [self.last_req[i][0], i];
						self.reqid += 1; 
			barrier3();
			self.last_req = self.new_req.copy();
			self.new_req = {};
				
			self.last_ans = self.new_ans.copy();
			self.new_ans = {};
			barrier3();

	def receive_ans_cache(self, addr, value): #primeste raspunsuri de la cache
		self.new_ans[addr] = value;

	def receive_req_processor(self, processor, rid, addr): #primeste cereri de la procesor
		if not rid in self.new_req:
			self.new_req[rid] = [];
		self.new_req[rid] = [processor, addr];


class Processor(GenericProcessor):
	def __init__(self, register_set, system_manager):
		GenericProcessor.__init__(self)
		self.__system_manager = system_manager;
		self.__register_set = register_set;
		self.state_idle = True;
		self.process_list = [];
		self.reqid = 0; 
		self.requests = {};
		self.answers = {};
		self.operation = [];
		self.operations = [];
		self.ans = 0;
		
	def run(self):
		global last_step;
		self.__system_manager.register_processor(self) 
		while last_step != 1:
			#starea idle
			if self.state_idle == True and len(self.process_list) > 0:
				
				self.operation = self.process_list[0].get_operation(self.process_list[0].get_number_of_executed_operations());
				self.__system_manager. processor_notify_start_executing_next_operation(self.process_list[0]);
				for  i in self.operation:
					if i != '*' and i != '+':
						self.__register_set.receive_req_processor(self, self.reqid, i);
						self.__system_manager.processor_notify_submit_request(self.__register_set, self.reqid, i);
						self.requests[i] = 0;
						self.reqid += 1;
				self.state_idle = False;

			#starea busy
			elif self.state_idle == False:
				
				if self.check_ans():
					if self.operation[0] == '*':
						self.ans = 1;
						for i in self.operation:
							if i != '*' and i != '+':
								self.ans *= self.answers[i];
					else:
						self.ans = 0;
						for i in self.operation:
							if i != '*' and i != '+':
								self.ans += self.answers[i];
					
					self.__system_manager.processor_notify_finish_executing_operation(self.ans);
					
					self.state_idle = True;
					self.process_list[0].inc_number_of_executed_operations();
					if self.process_list[0].get_number_of_executed_operations() == self.process_list[0].get_number_of_operations():
						self.process_list.pop(0);
					
					for i in self.operation:
						if i in self.answers:
							del self.answers[i];
					for i in self.operation:
						if i in self.requests:
							del self.requests[i];
						
			barrier3();
			barrier3();

	def receive_ans_regset(self, addr, value):
		if addr in self.requests and self.state_idle == False:
			del self.requests[addr];
			self.answers[addr] = value;

    	def receive_process(self, process):
		self.process_list.append(process);

	def check_ans(self):
		#verifica daca s-au primit raspunsuri pentru toate adresele necesare efectuarii operatiei
		for i in self.operation:
			if not i in self.answers and i != '*' and i != '+':
				return False;
		return True;
		
class ProcessScheduler(GenericProcessScheduler):
	def __init__(self, processor_list, system_manager):
		GenericProcessScheduler.__init__(self)
		self.__processor_list = processor_list;
		self.__system_manager = system_manager;
		self.process_list_ready_to_send = [];
		self.process_list = [];
		self.processor_index = 0;
	
	def submit_process(self, process):
		#metoda este apelata de system manager cu o instanta a clasei proces
		self.process_list.append(process);

	def run(self):
		global last_step;
		self.__system_manager.register_scheduler(self);
		while last_step != 1:
			for i in self.process_list_ready_to_send:
				self.__system_manager.scheduler_notify_submit_process(self.__processor_list[self.processor_index], i);
				self.__processor_list[self.processor_index].receive_process(i); #trimite un proces procesorului de la un anumit index
				self.processor_index += 1;
				if self.processor_index == len(self.__processor_list):
					self.processor_index = 0;
			self.process_list_ready_to_send = [];
			barrier3();
			self.process_list_ready_to_send = self.process_list;
			self.process_list = [];
			barrier3();
		

#la fiecare cerere de resurse se incrementeaza numarul de threaduri pentru folosirea lui in cadrul barierei
def get_RAM(num_ram_cells, num_ram_requests_per_time_step, system_manager):
	global threads, last_step;
	ram = RAM(system_manager, num_ram_cells, num_ram_requests_per_time_step);
	threads += 1;
	return ram;


def get_cache(num_cache_cells, ram, system_manager):
	global threads
	cache = Cache (num_cache_cells, ram, system_manager);
	threads += 1;
	return cache;

def get_register_set(num_register_cells, cache, system_manager):
	global threads
	reg_set = RegSet (num_register_cells, cache, system_manager);
	threads += 1;
	return reg_set;

def get_processor(register_set, system_manager):
	global threads
	processor = Processor (register_set, system_manager);
	threads += 1;
	return processor;

def get_process_scheduler(processor_list, system_manager):
	global threads
	processScheduler = ProcessScheduler (processor_list, system_manager);
	threads += 1;
	return processScheduler;

def init():
	#initializare variabile globale
	global threads, last_step, n;
	threads = 1;
	last_step = 0;
	n = threads;

