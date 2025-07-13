#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>

#include "contest_message.hh"
#include "controller.hh"
#include "timestamp.hh"
#include <deque>
#include <random>
#include <vector>

using namespace std;

// tcp variables
uint64_t has_send = 0;
uint64_t inflight = 0;
uint64_t delivered = 0;
double ssthresh = 100.0;

// vegas variables
// double expected_throughput = 0;
// double actual_throughput = 0;
double diff_throughput = 0;

double alpha = 4;
double beta = 6;
// double gammaa = 1;

uint64_t beg_snd_nxt = 0;
uint64_t beg_snd_una = 0;
uint64_t cnt_RTT = 0;
bool doing_vegas = false;
bool doing_reno = false;
bool doing_slow_start = false;
double baseRtt = 0;
double minRTT = 0;
double actualRTT;

double last_bandwidth = 0.0;
// cwnd
double target_cwnd = 0;
double cwnd = 10;

deque<double> baseRTT_filter;
const int filter_size = 2000;

// RTT estimation variables
double SRTT = 0;
double RTTVAR = 0;
double RTO = 1;
const double alpha_rtt = 0.125;
const double beta_rtt = 0.25;

// random variables
const int omega = 0;
int randoms = 100;
void update_rtt_and_rto(double actualRTT);
void print_paraments(uint64_t send_timestamp_acked,
                     uint64_t timestamp_ack_received,
                     uint64_t sequence_number_acked);

void vegas_ssthresh() { ssthresh = min(ssthresh, cwnd - 1); }

void current_ssthresh() { ssthresh = max(ssthresh, cwnd * 0.8); }

void adjustCwnd() {
  if (doing_slow_start) {
    if (cwnd >= ssthresh) {
      doing_slow_start = false;
    }
  }

  if (doing_vegas) {
    if (cnt_RTT < 2) {
      doing_vegas = false;
      doing_reno = true;
    }
  }

  if (doing_vegas) {

    beg_snd_nxt = has_send + 1;
    target_cwnd = cwnd * baseRtt / actualRTT;
    diff_throughput = cwnd * (actualRTT - baseRtt) / actualRTT;

    if (doing_slow_start) {
      cwnd = min(cwnd + 1, ssthresh);
    } else {
      if (diff_throughput > beta) {
        cwnd = max(1.0, cwnd - 0.7);
        vegas_ssthresh();
      } else if (diff_throughput < alpha) {
        cwnd = cwnd + 0.7;
      }
    }

    if (cwnd > ssthresh) {
      current_ssthresh();
    }
  } else if (doing_reno) {
    if (doing_slow_start) {
      cwnd += 2;
    } else {
      cwnd += 1 / cwnd;
      ssthresh = cwnd + 0.7;
    }
  }
}

void update_bandwidth_and_rtt(uint64_t send_timestamp, uint64_t ack_timestamp) {
  actualRTT = ack_timestamp - send_timestamp; // ms
  if (baseRTT_filter.size() >= filter_size) {
    baseRTT_filter.pop_front();
  }
  baseRTT_filter.push_back(actualRTT);
  baseRtt = std::numeric_limits<double>::max();
  for (size_t i = 0; i < baseRTT_filter.size(); i++) {
    baseRtt = min(baseRtt, baseRTT_filter[i]);
  }

  minRTT = min(minRTT, actualRTT);
  cnt_RTT++;
}

Controller::Controller(const bool debug) : debug_(debug) {
  baseRtt = numeric_limits<double>::max();
  minRTT = numeric_limits<double>::max();
  cwnd = 5;
  doing_slow_start = true;
  doing_vegas = true;
  doing_reno = false;
}

unsigned int Controller::window_size() {

  if (debug_) {
    cerr << "Current window size: " << cwnd << endl;
  }
  cwnd = max(cwnd, 1.0);
  // cwnd = min(cwnd, ssthresh);
  //  if (rand() % 100 < omega) {
  //    return  static_cast<uint64_t>(1);
  //  }

  return static_cast<uint64_t>(cwnd);
}

void Controller::datagram_was_sent(const uint64_t sequence_number,
                                   const uint64_t send_timestamp,
                                   const bool after_timeout) {
  if (debug_) {
    cerr << "Sent datagram " << sequence_number << " at " << send_timestamp
         << (after_timeout ? " due to timeout.\n" : ".\n");
  }
  has_send++;
  inflight = has_send - delivered;
  randoms = rand() % 100;
}

void Controller::ack_received(const uint64_t sequence_number_acked,
                              const uint64_t send_timestamp_acked,
                              const uint64_t recv_timestamp_acked,
                              const uint64_t timestamp_ack_received) {
  if (debug_) {
    cerr << "Ack received: Seq #" << sequence_number_acked << ", Sent at "
         << send_timestamp_acked << ", Recv at " << recv_timestamp_acked
         << ", Ack at " << timestamp_ack_received << endl;
  }
  delivered++;
  inflight = has_send - delivered;

  doing_vegas = true;
  doing_reno = false;
  update_bandwidth_and_rtt(send_timestamp_acked, timestamp_ack_received);
  update_rtt_and_rto(timestamp_ack_received - send_timestamp_acked);
  adjustCwnd();
  // print_paraments(send_timestamp_acked, timestamp_ack_received,
  //                 sequence_number_acked);
  randoms = rand() % 100;
}

void update_rtt_and_rto(double actualRTT) {
  if (SRTT == 0) {
    SRTT = actualRTT;
    RTTVAR = actualRTT / 2;
  } else {
    RTTVAR = (1 - beta_rtt) * RTTVAR + beta_rtt * fabs(SRTT - actualRTT);
    SRTT = (1 - alpha_rtt) * SRTT + alpha_rtt * actualRTT;
  }
  RTO = SRTT + 4 * RTTVAR;
}

unsigned int Controller::timeout_ms() {
  return static_cast<unsigned int>(RTO);
}

void print_paraments(uint64_t send_timestamp_acked,
                     uint64_t timestamp_ack_received,
                     uint64_t sequence_number_acked) {
  printf("sequence_number_acked: %lu\n", sequence_number_acked);
  printf("send_timestamp_acked: %lu\n", send_timestamp_acked);
  printf("timestamp_ack_received: %lu\n", timestamp_ack_received);
  printf("cwnd: %f\n", cwnd);
  printf("ssthresh: %f\n", ssthresh);
  printf("baseRtt: %f\n", baseRtt);
  printf("minRTT: %f\n", minRTT);
  printf("doing_vegas: %d\n", doing_vegas);
  printf("doing_reno: %d\n", doing_reno);
  printf("doing_slow_start: %d\n", doing_slow_start);
  printf("has_send: %lu\n", has_send);
  printf("inflight: %lu\n", inflight);
  printf("delivered: %lu\n", delivered);
  printf("target cwnd: %lf\n", target_cwnd);
  printf("diff_throughput: %f\n\n", diff_throughput);
}