// LingMetrics protocol wrapper; linked to the unchanged LAL v24.10 minimum API.
#include <lal/graphs/free_tree.hpp>
#include <lal/linarr/D/Dmin.hpp>
#include <iostream>
#include <regex>
#include <sstream>
#include <vector>
#include <numeric>

int main() {
    try {
        std::string input((std::istreambuf_iterator<char>(std::cin)),{});
        std::smatch match;
        if (!std::regex_search(input,match,std::regex("\"n\"\\s*:\\s*(\\d+)"))) return 2;
        const auto n=std::stoull(match[1]);
        if (n==0 || n>500) return 3;
        const auto start=input.find("\"edges\"");
        if (start==std::string::npos) return 4;
        const auto text=input.substr(start); const std::regex pair("\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]");
        lal::edge_list edges; std::vector<unsigned long long> parent(n);std::iota(parent.begin(),parent.end(),0);
        auto root=[&parent](unsigned long long x){while(parent[x]!=x)x=parent[x];return x;};
        for (auto it=std::sregex_iterator(text.begin(),text.end(),pair);it!=std::sregex_iterator();++it) {
            const auto a=std::stoull((*it)[1]), b=std::stoull((*it)[2]);
            if(a>=n || b>=n || a==b || root(a)==root(b)) return 5;
            parent[root(a)]=root(b);edges.emplace_back(a,b);
        }
        if(edges.size()!=n-1)return 6;
        lal::graphs::free_tree tree(n);tree.add_edges(edges);
        const auto result=lal::linarr::min_sum_edge_lengths(tree,lal::linarr::algorithms_Dmin::Shiloach);
        unsigned long long verified=0;
        for (const auto& e:edges) {
            const auto a=result.second.get_position_of(e.first), b=result.second.get_position_of(e.second);
            verified+=(a>b ? a-b : b-a);
        }
        if(verified!=result.first)return 7;
        std::cout<<"{\"minimum\":"<<result.first<<",\"exact\":true,\"algorithm\":\"LAL-24.10-Shiloach\",\"arrangement\":[";
        for(unsigned long long u=0;u<n;++u){if(u)std::cout<<",";std::cout<<result.second.get_position_of(u);}
        std::cout<<"]}\n";
    } catch (const std::exception& e){std::cerr<<e.what()<<"\n";return 8;}
}
