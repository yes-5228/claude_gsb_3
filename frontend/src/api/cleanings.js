import { http } from './client.js';

const RESOURCE = '/cleanings';

export const cleaningApi = {
  list: (params) => http.get(RESOURCE, params),
  schedule: (params) => http.get(`${RESOURCE}/schedule`, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
};
