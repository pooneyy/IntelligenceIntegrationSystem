# self.timeout_checker_thread = threading.Thread(target=self._check_timeout_worker, daemon=True)

# worker_count = max(1, os.cpu_count() // 2)
# self.processor_executor = ThreadPoolExecutor(
#     max_workers=worker_count,
#     thread_name_prefix="ProcessorWorker"
# )

# self.server_thread.start()
# self.archive_thread.start()
# self.processor_thread.start()
# self.timeout_checker_thread.start()







# with self.lock:
#     if uuid_str in self.processing_map:
# original_retry_count, original_data = self.processing_map.pop(uuid_str)
# combined_data = {**original_data, **processed_data}  # 合并数据

# del self.processing_map[uuid_str]
# self.processed_queue.put(validated_data)


# for _ in range(self.processor_executor._max_workers):
#     self.processor_executor.submit(self._processing_loop)


# self.timeout_checker_thread.start()


# for _ in range(self.processor_executor._max_workers * 2):
#     self.input_queue.put(None)


self.timeout_checker_thread.join(timeout=timeout)

# 5.关闭线程池
# self.processor_executor.shutdown(wait=True)
# logger.info("线程池已安全关闭")


# def _processing_loop(self):
#     while not self.shutdown_flag.is_set():
#         try:
#             data = self.input_queue.get(block=True)
#
#             # Shutdown will put None to make thread un-blocking
#             if not data:
#                 self.input_queue.task_done()
#                 continue
#
#             self._process_data(data)
#         except queue.Empty:
#             continue
#         except Exception as e:
#             logger.error(f"_processing_loop error: {str(e)}")
#         finally:
#             self.input_queue.task_done()
#
# def _process_data(self, data: dict):
#     try:
#         if 'prompt' not in data:
#             data['prompt'] = DEFAULT_ANALYSIS_PROMPT
#
#         data['PROMPT'] = data.pop('prompt')
#         data['TEXT'] = self._format_message_text(data)
#
#         uuid_str = data['UUID']
#         data[APPENDIX_TIME_POST] = time.time()
#
#         # Record data first avoiding request gets exception which makes data lost.
#         self.processing_map[uuid_str] = data
#
#         response = post_to_ai_processor(
#             self.intelligence_processor_uri,
#             self.data_without_appendix(data)
#         )
#         response.raise_for_status()
#
#         # TODO: If the request is actively rejected. Just drop this data.
#
#     except Exception as e:
#         logger.error(f"_process_data got error: {str(e)}")

# def _check_timeout_worker(self):
#     while not self.shutdown_flag.is_set():
#         current_time = time.time()
#
#         with self.lock:
#             uuids = list(self.processing_map.keys())
#             for _uuid in uuids:
#                 data = self.processing_map[_uuid]
#                 if APPENDIX_TIME_POST not in data:
#                     del self.processing_map[_uuid]
#                     self.drop_counter += 1
#                     logger.error(f'{data["uuid"]} has no must have fields - drop.')
#                     continue
#
#                 if APPENDIX_RETRY_COUNT not in data:
#                     data[APPENDIX_RETRY_COUNT] = self.intelligence_process_max_retries
#                 else:
#                     if data[APPENDIX_RETRY_COUNT] <= 0:
#                         del self.processing_map[_uuid]
#                         self.drop_counter += 1
#                         logger.error(f'{data["UUID"]} has no retry times - drop.')
#                         continue
#
#                 if current_time - data[APPENDIX_TIME_POST] > self.intelligence_process_timeout:
#                     data[APPENDIX_RETRY_COUNT] -= 1
#                     self.original_queue.put(data)
#
#         time.sleep(self.intelligence_process_timeout / 2)


# if not self.insert_data_into_mongo(data):
#     raise ValueError

# doc = self._create_document(data)
# doc_id = self.archive_col.insert_one(doc).inserted_id
#
# if 'embedding' in data:
#     self.vector_index.add_vector(doc_id, data['embedding'])


#
# def _format_message_text(self, data: dict) -> str:
#     appendix = []
#     if 'title' in data:
#         appendix.append(f"Title: {data['title']}")
#     if 'authors' in data:
#         appendix.append(f"Author: {data['authors']}")
#     if 'pub_time' in data:
#         appendix.append(f"Publish Time: {data['pub_time']}")
#     if 'informant' in data:
#         appendix.append(f"Informant: {data['informant']}")
#     return '\n'.join(appendix) + data['content']




















